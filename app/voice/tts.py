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
    Text-to-speech wrapper supporting ultra-natural edge-tts (delicate anime girl voice)
    with offline pyttsx3 fallback.
    """

    def __init__(self, enabled: bool = TTS_ENABLED):
        self.enabled = enabled
        self._engine = None
        self._engine_type = TTS_ENGINE
        self._lock   = threading.Lock()

    def _get_engine(self):
        """Lazy-initialise pyttsx3 fallback engine."""
        if self._engine is not None:
            return self._engine

        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate",   TTS_RATE or 185)
            engine.setProperty("volume", TTS_VOLUME or 1.0)

            # Auto-select female voice
            try:
                voices = engine.getProperty("voices")
                female_voice = None
                for v in (voices or []):
                    name_l = v.name.lower()
                    if "zira" in name_l or "female" in name_l or "eva" in name_l:
                        female_voice = v.id
                        break
                if female_voice:
                    engine.setProperty("voice", female_voice)
            except Exception as v_err:
                logger.warning("Could not set female voice: %s", v_err)

            self._engine = ("pyttsx3", engine)
            logger.info("TTS fallback engine (pyttsx3) initialised.")
            return self._engine
        except Exception as exc:
            logger.warning("pyttsx3 init failed: %s", exc)
            return None

    def is_available(self) -> bool:
        """Return True if a TTS engine is available."""
        try:
            import edge_tts
            return True
        except ImportError:
            return self._get_engine() is not None

    async def _generate_edge_tts_bytes(self, text: str) -> bytes:
        """Synthesize ultra-delicate anime girl voice via edge-tts."""
        import edge_tts
        has_devanagari = any('\u0900' <= ch <= '\u097f' for ch in text)
        if has_devanagari:
            # Native delicate Marathi female voice
            voice = "mr-IN-AarohiNeural"
            pitch = "+8Hz"
            rate  = "+2%"
        else:
            # 18-year-old sweet, charming anime girl voice (Ava Multilingual)
            voice = "en-US-AvaMultilingualNeural"
            pitch = "+18Hz"
            rate  = "+5%"

        comm = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    async def synthesize_bytes_async(self, text: str) -> Optional[bytes]:
        """Asynchronously return MP3 bytes using edge-tts."""
        clean = clean_text_for_speech(text)
        if not clean:
            return None
        try:
            return await self._generate_edge_tts_bytes(clean)
        except Exception as e:
            logger.warning("edge-tts async synthesis failed: %s", e)
            return None

    def synthesize_bytes(self, text: str) -> Optional[bytes]:
        """Synchronously return MP3 bytes using edge-tts."""
        clean = clean_text_for_speech(text)
        if not clean:
            return None
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(self._generate_edge_tts_bytes(clean))).result()
            else:
                return asyncio.run(self._generate_edge_tts_bytes(clean))
        except Exception as e:
            logger.warning("edge-tts synthesis failed, falling back: %s", e)
            return None


    def get_voices(self) -> list[dict]:
        """Return list of available system voices."""
        return [
            {"id": "en-US-AnaNeural", "name": "NOVA Anime Voice (Delicate & Sweet)"},
            {"id": "mr-IN-AarohiNeural", "name": "Aarohi (Marathi Female)"},
            {"id": "pyttsx3", "name": "Local Windows SAPI5 (Offline)"},
        ]

    def clean_and_speak(self, text: str, block: bool = False) -> None:
        """Sanitize text and speak it aloud."""
        clean = clean_text_for_speech(text)
        if clean:
            self.speak(clean, block=block)

    def speak(self, text: str, block: bool = False) -> None:
        """Speak text aloud using delicate anime voice."""
        if not self.enabled:
            logger.debug("TTS disabled — skipping speech.")
            return
        if not text.strip():
            return

        def _do_speak():
            with self._lock:
                # 1. Try edge-tts delicate anime voice with soundfile + sounddevice
                try:
                    import io
                    import soundfile as sf
                    import sounddevice as sd
                    audio_bytes = self.synthesize_bytes(text)
                    if audio_bytes:
                        data, fs = sf.read(io.BytesIO(audio_bytes))
                        sd.play(data, fs)
                        if block:
                            sd.wait()
                        return
                except Exception as edge_err:
                    logger.warning("edge-tts playback error: %s. Using pyttsx3 fallback.", edge_err)

                # 2. Offline pyttsx3 fallback
                try:
                    res = self._get_engine()
                    if res and res[0] == "pyttsx3":
                        engine = res[1]
                        engine.say(text)
                        engine.runAndWait()
                except Exception as exc:
                    logger.error("TTS speak fallback error: %s", exc)

        if block:
            _do_speak()
        else:
            t = threading.Thread(target=_do_speak, daemon=True)
            t.start()

    def stop(self) -> None:
        """Stop any ongoing speech."""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
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

