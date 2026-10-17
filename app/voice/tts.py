"""
NOVA Voice Output — Offline Text-to-Speech
-------------------------------------------
Default engine : pyttsx3  (uses OS native TTS — no downloads needed)
Alternative    : Set NOVA_TTS_ENGINE=kokoro or edge-tts in .env for better quality.
                 (edge-tts requires internet; kokoro requires model download)

pyttsx3 uses:
  - Windows: SAPI5 (built-in, works offline)
  - Linux  : espeak (install: sudo apt install espeak)
  - macOS  : NSSpeechSynthesizer

Raspberry Pi:
  pyttsx3 with espeak works on Pi. Install:  sudo apt install espeak python3-espeak
"""

import re
import threading
from pathlib import Path
from typing import Optional

from app.core.config import TTS_ENGINE, TTS_ENABLED, TTS_RATE, TTS_VOLUME, PIPER_DIR
from app.core.logger import get_logger

logger = get_logger(__name__)


def clean_text_for_speech(text: str) -> str:
    """
    Sanitize text before speech synthesis:
      - Replace fenced code blocks with a brief spoken placeholder
      - Strip markdown asterisks, hashes, backticks, strikethroughs
      - Convert markdown links [text](url) to just text
      - Strip URLs, emojis, and decorative bullet symbols
      - Collapse repeated whitespace
    """
    if not text:
        return ""

    s = text

    # Replace fenced code blocks (```...```)
    s = re.sub(r"```[a-zA-Z0-9_-]*\n[\s\S]*?```", " Code block omitted. ", s)
    s = re.sub(r"```[\s\S]*?```", " Code block omitted. ", s)

    # Inline code: `code` -> code
    s = re.sub(r"`([^`]+)`", r"\1", s)

    # Markdown links: [Title](url) -> Title
    s = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", s)

    # Strip raw URLs
    s = re.sub(r"https?://\S+", "", s)

    # Strip markdown headers (# Header)
    s = re.sub(r"^[ \t]*#+[ \t]+", "", s, flags=re.MULTILINE)

    # Strip bold / italics / strikethrough: **, *, __, _, ~~
    s = re.sub(r"(\*\*|__)(.*?)\1", r"\2", s)
    s = re.sub(r"(\*|_)(.*?)\1", r"\2", s)
    s = re.sub(r"~~(.*?)~~", r"\1", s)

    # Strip blockquotes (> Quote)
    s = re.sub(r"^[ \t]*>[ \t]*", "", s, flags=re.MULTILINE)

    # Strip bullet indicators (- , * , + , 1. )
    s = re.sub(r"^[ \t]*[-*+]\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"^[ \t]*\d+\.\s+", "", s, flags=re.MULTILINE)

    # Strip horizontal rules
    s = re.sub(r"^[-*_]{3,}\s*$", "", s, flags=re.MULTILINE)

    # Strip emojis and special symbols
    s = re.sub(r"[\U00010000-\U0010ffff]", "", s)

    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


class TTSEngine:
    """
    Offline text-to-speech wrapper supporting pyttsx3 and Piper TTS.
    """

    def __init__(self, enabled: bool = TTS_ENABLED):
        self.enabled = enabled
        self._engine = None
        self._engine_type = TTS_ENGINE
        self._lock   = threading.Lock()     # pyttsx3 is not thread-safe

    def _get_engine(self):
        """Lazy-initialise TTS engine."""
        if self._engine is not None:
            return self._engine

        if self._engine_type == "piper":
            # Check for Piper onnx voice models in PIPER_DIR
            onnx_files = list(PIPER_DIR.glob("*.onnx"))
            if onnx_files:
                try:
                    import piper
                    logger.info("Piper TTS model found: %s", onnx_files[0])
                    self._engine = ("piper", str(onnx_files[0]))
                    return self._engine
                except ImportError:
                    logger.warning("piper-tts package not importable. Falling back to pyttsx3.")

        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate",   TTS_RATE)
            engine.setProperty("volume", TTS_VOLUME)
            self._engine = ("pyttsx3", engine)
            logger.info("TTS engine (pyttsx3) initialised.")
            return self._engine
        except ImportError:
            raise RuntimeError("pyttsx3 not installed. Run: pip install pyttsx3")
        except Exception as exc:
            raise RuntimeError(f"TTS engine failed to init: {exc}")

    def is_available(self) -> bool:
        """Return True if a TTS engine is available."""
        try:
            self._get_engine()
            return True
        except Exception:
            return False

    def get_voices(self) -> list[dict]:
        """Return list of available system voices."""
        try:
            eng_type, engine = self._get_engine()
            if eng_type == "pyttsx3":
                voices = engine.getProperty("voices")
                return [{"id": v.id, "name": v.name} for v in (voices or [])]
            return [{"id": "piper", "name": "Piper Neural Voice"}]
        except Exception:
            return []

    def clean_and_speak(self, text: str, block: bool = False) -> None:
        """Sanitize text and speak it aloud."""
        clean = clean_text_for_speech(text)
        if clean:
            self.speak(clean, block=block)

    def speak(self, text: str, block: bool = False) -> None:
        """
        Speak text aloud.
        """
        if not self.enabled:
            logger.debug("TTS disabled — skipping speech.")
            return
        if not text.strip():
            return

        def _do_speak():
            with self._lock:
                try:
                    eng_type, engine = self._get_engine()
                    if eng_type == "pyttsx3":
                        engine.say(text)
                        engine.runAndWait()
                except Exception as exc:
                    logger.error("TTS speak error: %s", exc)

        if block:
            _do_speak()
        else:
            t = threading.Thread(target=_do_speak, daemon=True)
            t.start()

    def stop(self) -> None:
        """Stop any ongoing speech."""
        try:
            if self._engine and self._engine[0] == "pyttsx3":
                self._engine[1].stop()
        except Exception:
            pass

    def set_enabled(self, value: bool) -> None:
        """Toggle TTS on/off at runtime."""
        self.enabled = value
        logger.info("TTS %s", "enabled" if value else "disabled")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_tts_instance: Optional[TTSEngine] = None


def get_tts() -> TTSEngine:
    """Return the module-level TTSEngine singleton."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSEngine()
    return _tts_instance

