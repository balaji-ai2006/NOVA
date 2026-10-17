"""
NOVA Voice API
--------------
POST /api/voice/transcribe   — upload a WAV file, get transcription text
POST /api/voice/tts/speak    — (debug) speak text via pyttsx3 server-side
GET  /api/voice/status       — availability check
"""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.voice.stt import get_stt
from app.voice.tts import get_tts
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class TTSRequest(BaseModel):
    text: str


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
):
    """
    Accept an audio file (WAV, WebM, OGG recorded by the browser) and return the transcription.
    Supports auto language detection or specific language (en, hi, mr).
    """
    stt = get_stt()
    if not stt.is_available():
        raise HTTPException(
            status_code=503,
            detail="faster-whisper is not installed. Run: pip install faster-whisper",
        )

    # Save upload to a temp file
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content  = await file.read()
        tmp.write(content)

    # Pass language: if 'auto' or None, Whisper will auto-detect acoustic language
    target_lang = None if (not language or language in ("auto", "none")) else language

    try:
        detailed = stt.transcribe_file_detailed(tmp_path, language=target_lang)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "transcription": detailed["text"],
        "length_chars": len(detailed["text"]),
        "detected_language": detailed["detected_language"],
        "confidence": detailed["confidence"],
        "is_auto": detailed["is_auto"],
    }


@router.post("/tts/speak")
async def tts_speak(req: TTSRequest):
    """
    Speak sanitized text server-side using local TTS.
    """
    tts = get_tts()
    if not tts.is_available():
        raise HTTPException(status_code=503, detail="TTS engine not available.")
    if not tts.enabled:
        return {"status": "tts_disabled", "message": "Enable TTS in settings."}
    tts.clean_and_speak(req.text, block=False)
    return {"status": "speaking"}


@router.post("/tts/stop")
async def tts_stop():
    """Stop any currently playing speech."""
    tts = get_tts()
    tts.stop()
    return {"status": "stopped"}


@router.post("/tts/clean")
async def tts_clean(req: TTSRequest):
    """Return speech-sanitized version of markdown text."""
    from app.voice.tts import clean_text_for_speech
    cleaned = clean_text_for_speech(req.text)
    return {"cleaned": cleaned}


@router.get("/status")
async def voice_status():
    """Return STT and TTS availability."""
    stt = get_stt()
    tts = get_tts()
    return {
        "stt": {
            "available": stt.is_available(),
            "engine":    "faster-whisper",
            "model":     stt.model_size,
            "device":    stt.device,
            "language":  stt.language or "auto (mr/hi/en)",
        },
        "tts": {
            "available": tts.is_available(),
            "enabled":   tts.enabled,
            "engine":    tts._engine_type,
            "voices":    tts.get_voices()[:5],
        },
    }
