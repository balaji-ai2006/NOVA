"""
NOVA Brain — Local LLM via Ollama
-----------------------------------
This module wraps the Ollama REST API to:
  - Check if Ollama is running and which models are installed
  - Send chat messages with streaming support
  - Keep short-term conversation context

Architecture note (Raspberry Pi):
  Ollama runs as a separate process on the same machine; this module
  talks to it over HTTP, so the same code works on Pi if Ollama is installed.
"""

import json
import re
from typing import Generator, Optional
from dataclasses import dataclass, field

import httpx  # lightweight async-compatible HTTP client

from app.core.config import (
    OLLAMA_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLM_TIMEOUT,
    LLM_STREAM,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    SHORT_TERM_TURNS,
)
from app.brain.prompts import NOVA_SYSTEM_PROMPT, get_system_prompt
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """Represents one chat message turn."""
    role: str          # "user" | "assistant" | "system"
    content: str


@dataclass
class BrainStatus:
    """Snapshot of local AI readiness."""
    ollama_running: bool = False
    available_models: list[str] = field(default_factory=list)
    selected_model: str = DEFAULT_LLM_MODEL
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class OllamaClient:
    """
    Thin wrapper around the Ollama HTTP API with multi-session support.

    All methods use *synchronous* httpx so they can be called from
    FastAPI background tasks or plain Python scripts without an event loop.
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_LLM_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self._sessions: dict[str, list[Message]] = {"default": []}

    @property
    def _history(self) -> list[Message]:
        """Backward compatibility property returning the default session history."""
        return self._sessions.setdefault("default", [])

    @_history.setter
    def _history(self, val: list[Message]) -> None:
        self._sessions["default"] = val

    # ------------------------------------------------------------------ #
    # Health / discovery                                                   #
    # ------------------------------------------------------------------ #

    def get_status(self) -> BrainStatus:
        """
        Check if Ollama is reachable and list available models.
        Returns a BrainStatus object (never raises).
        """
        status = BrainStatus(selected_model=self.model)
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            status.ollama_running   = True
            status.available_models = [m["name"] for m in data.get("models", [])]
            logger.info("Ollama running. Models: %s", status.available_models)
        except httpx.ConnectError:
            status.error = (
                "Ollama is not running. Start it with: ollama serve\n"
                "Then pull a model: ollama pull llama3.2:3b"
            )
            logger.warning("Ollama not reachable at %s", self.base_url)
        except Exception as exc:
            status.error = f"Unexpected error contacting Ollama: {exc}"
            logger.error(status.error)
        return status

    def is_model_available(self) -> bool:
        """Return True if the configured model exists in the local Ollama library."""
        status = self.get_status()
        if not status.ollama_running:
            return False
        return any(m.startswith(self.model.split(":")[0]) for m in status.available_models)

    def pull_instructions(self) -> str:
        """Return human-readable instructions for pulling the default model."""
        return (
            f"Model '{self.model}' is not downloaded yet.\n"
            f"Run this command once (requires internet):\n\n"
            f"    ollama pull {self.model}\n\n"
            f"After downloading, NOVA will work fully offline."
        )

    # ------------------------------------------------------------------ #
    # Chat & Sessions                                                      #
    # ------------------------------------------------------------------ #

    def add_system_prompt(self, system_text: str, session_id: str = "default") -> None:
        """Prepend a system message for a specific session."""
        session = self._sessions.setdefault(session_id, [])
        self._sessions[session_id] = [m for m in session if m.role != "system"]
        self._sessions[session_id].insert(0, Message(role="system", content=system_text))

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        extra_context: Optional[str] = None,
        session_id: str = "default",
        stream: bool = LLM_STREAM,
        response_language: str = "en",
    ) -> Generator[str, None, None]:
        """
        Send a message to Ollama and yield the response token by token.
        Maintains conversational context inside the specified session_id.
        """
        status = self.get_status()
        if not status.ollama_running:
            raise RuntimeError(status.error or "Ollama is not running.")

        if not status.available_models:
            raise RuntimeError(
                f"No local models found.\n{self.pull_instructions()}"
            )

        messages: list[dict] = []

        # System prompt with intelligent persona and response language preference
        _sys = system_prompt or get_system_prompt(response_language=response_language)
        messages.append({"role": "system", "content": _sys})

        # Inject extra context (e.g. relevant memory, camera description)
        if extra_context:
            messages.append({"role": "user",      "content": f"[Context Information]\n{extra_context}"})
            messages.append({"role": "assistant", "content": "Acknowledged. I will incorporate this context into my response."})

        # Session history (last N turns)
        session_history = self._sessions.setdefault(session_id, [])
        history = [m for m in session_history if m.role != "system"][-SHORT_TERM_TURNS:]
        for m in history:
            messages.append({"role": m.role, "content": m.content})

        # Enforce user response language preference
        if response_language == "en":
            user_low = user_message.lower()
            explicit_other = any(w in user_low for w in ["मराठीत", "in marathi", "in hindi", "हिंदी में"])
            if not explicit_other:
                messages.append({
                    "role": "system",
                    "content": "IMPORTANT: Formulate your entire reply in ENGLISH. The user has selected English response mode."
                })
        elif response_language == "mr":
            messages.append({
                "role": "system",
                "content": "IMPORTANT: Formulate your entire reply in MARATHI (मराठी)."
            })
        elif response_language == "hi":
            messages.append({
                "role": "system",
                "content": "IMPORTANT: Formulate your entire reply in HINDI (हिन्दी)."
            })

        # Current user turn
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model":    self.model,
            "messages": messages,
            "stream":   stream,
            "options": {
                "num_predict": LLM_MAX_TOKENS,
                "temperature": LLM_TEMPERATURE,
            },
        }

        logger.info("-> LLM [%s] (session=%s) user: %s", self.model, session_id, user_message[:80].encode('ascii', errors='replace').decode('ascii'))

        try:
            full_response = ""
            inside_think_block = False

            with httpx.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=LLM_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        # Guard against reasoning models leaking internal thinking tags
                        if "<think>" in token:
                            inside_think_block = True
                            token = token.replace("<think>", "")
                        if "</think>" in token:
                            inside_think_block = False
                            token = token.replace("</think>", "")
                            continue
                        if inside_think_block:
                            continue

                        if token:
                            full_response += token
                            yield token

                    if chunk.get("done"):
                        break

            # Strip any residual thinking tags
            full_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL).strip()

            if not full_response:
                fallback = "I processed your request, but received an empty response. Please rephrase or try again."
                yield fallback
                full_response = fallback

            # Store the exchange in session history
            session_history.append(Message(role="user",      content=user_message))
            session_history.append(Message(role="assistant", content=full_response))
            logger.info("<- LLM response (%d chars)", len(full_response))

        except httpx.ReadTimeout:
            raise RuntimeError(
                f"Ollama timed out after {LLM_TIMEOUT}s. "
                "The model might be taking too long. Please try again or simplify the query."
            )
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama HTTP error: {exc.response.status_code} — {exc.response.text}")

    def clear_history(self, session_id: str = "default") -> None:
        """Wipe conversation history for a given session."""
        self._sessions[session_id] = []
        logger.info("Conversation history cleared for session: %s", session_id)

    def get_history(self, session_id: str = "default") -> list[Message]:
        """Return a copy of the short-term history for a session."""
        return list(self._sessions.setdefault(session_id, []))

    def set_model(self, model_name: str) -> None:
        """Switch to a different local model."""
        self.model = model_name
        logger.info("Model switched to: %s", model_name)
