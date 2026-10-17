"""
NOVA Status API
---------------
GET  /api/status/           — full system status (Ollama, memory, voice, vision)
GET  /api/status/ollama     — Ollama-specific status
GET  /api/status/system     — CPU / RAM / disk usage
"""

from fastapi import APIRouter
from app.brain.ollama_client import OllamaClient
from app.memory.store import MemoryStore
from app.voice.stt import get_stt
from app.voice.tts import get_tts
from app.vision.camera import get_camera, get_vision
from app.tools.computer import get_system_info
from app.core.config import (
    APP_NAME, APP_VERSION, DEFAULT_LLM_MODEL,
    TTS_ENABLED, VISION_ENABLED, OFFLINE_MODE,
)

router  = APIRouter()
_client = OllamaClient()
_memory = MemoryStore()


@router.get("/")
async def full_status():
    """Return the complete NOVA system status for the dashboard."""
    ollama_status = _client.get_status()

    stt = get_stt()
    tts = get_tts()
    cam = get_camera()
    vis = get_vision()

    return {
        "app": {
            "name":         APP_NAME,
            "version":      APP_VERSION,
            "offline_mode": OFFLINE_MODE,
        },
        "llm": {
            "running":          ollama_status.ollama_running,
            "selected_model":   _client.model,
            "available_models": ollama_status.available_models,
            "error":            ollama_status.error,
        },
        "memory": {
            "count": len(_memory.list_all()),
        },
        "voice": {
            "stt_available": stt.is_available(),
            "stt_engine":    "faster-whisper",
            "tts_available": tts.is_available(),
            "tts_enabled":   tts.enabled,
        },
        "vision": {
            "camera_available":  cam.is_available(),
            "vision_model":      vis.model,
            "vision_llm_ready":  vis.is_model_available(),
        },
    }


@router.get("/ollama")
async def ollama_status():
    """Check Ollama availability and list local models."""
    s = _client.get_status()
    return {
        "running":    s.ollama_running,
        "models":     s.available_models,
        "error":      s.error,
        "pull_hint":  _client.pull_instructions() if not s.available_models else None,
    }


@router.get("/system")
async def system_status():
    """Return CPU, RAM, and disk usage."""
    return get_system_info()
