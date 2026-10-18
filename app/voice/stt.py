"""
NOVA Voice Input — Offline Speech-to-Text
------------------------------------------
Primary engine : faster-whisper (OpenAI Whisper distilled, runs on CPU & CUDA)
Fallback note  : Vosk can be used instead by changing STT_ENGINE in .env

Push-to-talk flow
-----------------
1. Frontend sends POST /api/voice/listen
2. This module records from the mic (or receives a WAV file)
3. Returns transcribed text

Raspberry Pi:
  faster-whisper works on Pi 4/5 (slow on tiny model).
  Set STT_DEVICE=cpu and STT_MODEL=tiny in .env for Pi.
"""

import io
import tempfile
import wave
from pathlib import Path
from typing import Optional

from app.core.config import STT_ENGINE, STT_MODEL, STT_LANGUAGE, STT_DEVICE
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# PyAV compatibility patch (for av >= 19.0 compatibility with faster-whisper)
# ---------------------------------------------------------------------------
try:
    import av
    _orig_av_open = av.open
    def _patched_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _patched_av_open
except Exception:
    pass

# ---------------------------------------------------------------------------
# Helper: choose compute device
# ---------------------------------------------------------------------------

def _resolve_device() -> tuple[str, str]:
    """
    Returns (device, compute_type) for faster-whisper.
    Auto-selects CUDA if available, falls back to CPU.
    """
    if STT_DEVICE == "cpu":
        return "cpu", "int8"
    if STT_DEVICE == "cuda":
        return "cuda", "float16"
    # Auto
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("STT: CUDA detected — using GPU acceleration.")
            return "cuda", "float16"
    except ImportError:
        pass
    logger.info("STT: Using CPU (int8 quantised Whisper).")
    return "cpu", "int8"


# ---------------------------------------------------------------------------
# WhisperSTT
# ---------------------------------------------------------------------------

class WhisperSTT:
    """
    Offline speech-to-text using faster-whisper.

    The model is loaded lazily on first use so startup stays fast.
    Model files are cached by faster-whisper in ~/.cache/huggingface/ automatically.
    Supports English, Marathi (mr), Hindi (hi), and auto-detection.
    """

    def __init__(self):
        self._model = None
        self.device, self.compute_type = _resolve_device()
        self.model_size = STT_MODEL        # tiny | base | small | medium | large-v3
        # If language is 'auto' or empty, pass None to Whisper for auto-detection
        raw_lang = (STT_LANGUAGE or "").strip().lower()
        self.language = None if raw_lang in ("auto", "", "none") else raw_lang

    def _load_model(self):
        """Lazy-load the Whisper model (downloads on first use if not cached)."""
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel  # type: ignore
            logger.info(
                "Loading faster-whisper model '%s' on %s…",
                self.model_size, self.device,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded successfully.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed.\n"
                "Install it with:  pip install faster-whisper"
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to load Whisper model: {exc}")

    def is_available(self) -> bool:
        """Return True if faster-whisper can be imported (model not yet needed)."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe_file_detailed(self, audio_path: str | Path, language: Optional[str] = None) -> dict:
        """
        Transcribe an audio file on disk (WAV, WebM, MP3, OGG).
        Automatically detects spoken language if language is None or 'auto'.

        Returns
        -------
        dict: {
            "text": str,
            "detected_language": str,
            "confidence": float,
            "is_auto": bool
        }
        """
        self._load_model()
        target_lang = language if language is not None else self.language
        if target_lang in ("auto", "none", "", None):
            target_lang = None

        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=target_lang,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=True,              # voice-activity detection = skip silence
                initial_prompt="Nova, Balaji, YouTube, Chrome, Google, Marathi, Hindi, YouTube var, gaana lav, gaan lav, play song, open kar, suru kar, यूट्यूब, गाणं लाव, गाणी, सर्च कर",
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            detected = getattr(info, "language", "unknown") if info else "unknown"
            prob = round(float(getattr(info, "language_probability", 1.0) or 0.0), 3) if info else 1.0
            logger.info("STT transcribed (lang=%s, conf=%.2f, requested=%s): %s", detected, prob, target_lang, text[:80])
            return {
                "text": text,
                "detected_language": detected,
                "confidence": prob,
                "is_auto": target_lang is None,
            }
        except Exception as exc:
            logger.error("STT transcription error: %s", exc)
            raise RuntimeError(f"Transcription failed: {exc}")

    def transcribe_file(self, audio_path: str | Path, language: Optional[str] = None) -> str:
        """
        Transcribe an audio file on disk and return the transcribed text.
        Backward-compatible wrapper around transcribe_file_detailed.
        """
        return self.transcribe_file_detailed(audio_path, language=language)["text"]

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe raw PCM audio bytes (16-bit, mono).
        Wraps bytes into a temporary WAV file then calls transcribe_file.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)          # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
        try:
            return self.transcribe_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# MicRecorder — synchronous, push-to-talk style
# ---------------------------------------------------------------------------

class MicRecorder:
    """
    Records a fixed-duration audio clip from the default microphone.
    Requires PyAudio (pip install pyaudio).

    This is intentionally simple: press button → record N seconds → return bytes.
    A proper VAD-based recorder would be a future improvement.
    """

    def __init__(self, duration: float = 5.0, sample_rate: int = 16000):
        self.duration    = duration
        self.sample_rate = sample_rate

    def is_available(self) -> bool:
        """Return True if PyAudio is importable and a mic is present."""
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            info = pa.get_default_input_device_info()
            pa.terminate()
            return True
        except Exception:
            return False

    def record(self) -> bytes:
        """
        Record `self.duration` seconds of audio from the default microphone.

        Returns
        -------
        Raw PCM bytes (16-bit, mono, 16000 Hz).

        Raises
        ------
        RuntimeError if PyAudio is not installed or no mic is found.
        """
        try:
            import pyaudio
        except ImportError:
            raise RuntimeError(
                "PyAudio is not installed. Run:  pip install pyaudio\n"
                "(On Windows you may need: pip install pipwin && pipwin install pyaudio)"
            )

        pa     = pyaudio.PyAudio()
        chunk  = 1024
        frames = []

        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=chunk,
            )
            logger.info("Recording for %.1f seconds…", self.duration)
            n_chunks = int(self.sample_rate / chunk * self.duration)
            for _ in range(n_chunks):
                frames.append(stream.read(chunk, exception_on_overflow=False))
            stream.stop_stream()
            stream.close()
        except OSError as exc:
            raise RuntimeError(
                f"Microphone error: {exc}\n"
                "Make sure a microphone is connected and not in use by another app."
            )
        finally:
            pa.terminate()

        return b"".join(frames)


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------
_stt_instance: Optional[WhisperSTT] = None


def get_stt() -> WhisperSTT:
    """Return the module-level WhisperSTT singleton."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = WhisperSTT()
    return _stt_instance
