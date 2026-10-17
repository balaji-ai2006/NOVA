"""
NOVA Chat API
-------------
POST /api/chat/send         — send a message, get streaming SSE response
POST /api/chat/clear        — clear conversation history
GET  /api/chat/history      — retrieve current session history
POST /api/chat/model        — switch LLM model
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.brain.ollama_client import OllamaClient
from app.memory.store import MemoryStore
from app.core.config import DEFAULT_LLM_MODEL
from app.core.logger import get_logger

logger   = get_logger(__name__)
router   = APIRouter()

# Module-level singletons (one conversation session per server)
_client  = OllamaClient()
_memory  = MemoryStore()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    include_memory: bool = True   # inject long-term memories into context
    response_language: Optional[str] = "en"   # default is English unless user explicitly selects otherwise


class ClearRequest(BaseModel):
    session_id: str = "default"


class ModelSwitchRequest(BaseModel):
    model: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/send")
async def send_message(req: ChatRequest):
    """
    Send a message to the local LLM and stream the response via SSE.

    SSE format: data: <json>\n\n
    Each chunk: {"token": "...", "done": false}
    Final:      {"token": "",   "done": true, "model": "..."}
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Retrieve memories specifically relevant to user's question
    extra_ctx: Optional[str] = None
    if req.include_memory:
        extra_ctx = _memory.as_context_string(query=req.message) or None

    def event_stream():
        try:
            for token in _client.chat(
                user_message=req.message,
                extra_context=extra_ctx,
                session_id=req.session_id,
                response_language=req.response_language or "en",
            ):
                data = json.dumps({"token": token, "done": False})
                yield f"data: {data}\n\n"

            # Signal completion
            final = json.dumps({
                "token": "",
                "done":  True,
                "model": _client.model,
                "session_id": req.session_id,
            })
            yield f"data: {final}\n\n"

        except RuntimeError as exc:
            err = json.dumps({"error": str(exc), "done": True})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",   # Nginx: disable buffering
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/clear")
async def clear_history(req: Optional[ClearRequest] = None):
    """Clear the in-memory conversation history for the specified session."""
    sid = req.session_id if req else "default"
    _client.clear_history(session_id=sid)
    return {"status": "ok", "session_id": sid, "message": f"Conversation history for '{sid}' cleared."}


@router.get("/history")
async def get_history(session_id: str = "default"):
    """Return the current short-term conversation history for a session."""
    history = _client.get_history(session_id=session_id)
    return {
        "model":      _client.model,
        "session_id": session_id,
        "history":    [{"role": m.role, "content": m.content} for m in history],
    }


@router.post("/model")
async def switch_model(req: ModelSwitchRequest):
    """Switch the active LLM model (takes effect on next message)."""
    # Check if model exists in Ollama
    status = _client.get_status()
    if req.model not in status.available_models:
        available = status.available_models
        raise HTTPException(
            status_code=404,
            detail=(
                f"Model '{req.model}' is not installed in Ollama.\n"
                f"Available: {available}\n"
                f"Pull it with: ollama pull {req.model}"
            ),
        )
    _client.set_model(req.model)
    _client.clear_history()  # fresh start when switching model
    return {"status": "ok", "model": req.model}
