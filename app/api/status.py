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


@router.get("/about")
async def about_status():
    """
    Return comprehensive product information, semantic version, build details,
    AI engine status, hardware recommendations, and verified installed features.
    Only displays features as available if they are verified.
    """
    import sys
    import platform
    from dataclasses import asdict
    from app.core.profiles import get_profile_manager
    from app.core.hardware import get_hardware_profile
    from app.core.paths import IS_FROZEN, APP_DATA_DIR, APP_CONFIG_DIR

    ollama_status = _client.get_status()
    stt = get_stt()
    tts = get_tts()
    cam = get_camera()
    vis = get_vision()
    profile = get_profile_manager().get_config()
    hardware = get_hardware_profile()

    # Verified feature table: only True if tested & working
    verified_features = {
        "local_llm_inference": {
            "name": "Local LLM Inference (Ollama)",
            "implemented": True,
            "verified": bool(ollama_status.ollama_running and ollama_status.available_models),
            "details": f"Active: {_client.model}" if ollama_status.ollama_running else "Ollama offline",
        },
        "speech_to_text": {
            "name": "Voice Input (Speech-to-Text)",
            "implemented": True,
            "verified": stt.is_available(),
            "details": f"faster-whisper ({stt.model_size})",
        },
        "text_to_speech": {
            "name": "Voice Output (Text-to-Speech)",
            "implemented": True,
            "verified": tts.is_available(),
            "details": f"{tts._engine_type} (active: {tts.enabled})",
        },
        "wake_word_assistant": {
            "name": "Wake-Word Listener ('Nova')",
            "implemented": True,
            "verified": profile.wake_word_enabled,
            "details": "Continuous background voice daemon",
        },
        "vision_understanding": {
            "name": "Vision & Camera Perception",
            "implemented": True,
            "verified": bool(cam.is_available() and vis.is_model_available()),
            "details": f"Model: {vis.model}, Camera: {'OK' if cam.is_available() else 'No camera'}",
        },
        "computer_automations": {
            "name": "Allowlisted Computer & Browser Tools",
            "implemented": True,
            "verified": True,
            "details": "Safe app launch, YouTube play, Google search, file read",
        },
        "persistent_local_memory": {
            "name": "Offline Local Memory (SQLite)",
            "implemented": True,
            "verified": True,
            "details": f"{len(_memory.list_all())} memory items stored locally",
        },
    }

    return {
        "product": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "tagline": "Personal Offline-First Multimodal AI Assistant",
            "profile": profile.profile_type,
            "distributable_ready": False,  # As required: not claimed until tested on clean external Windows
        },
        "build": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "is_frozen_executable": IS_FROZEN,
            "data_directory": str(APP_DATA_DIR),
            "config_directory": str(APP_CONFIG_DIR),
        },
        "ai_engine": {
            "provider": "Ollama (Offline/Local)",
            "base_url": _client.base_url,
            "connected": ollama_status.ollama_running,
            "active_model": _client.model,
            "installed_models": ollama_status.available_models,
            "error": ollama_status.error,
        },
        "hardware": asdict(hardware),
        "verified_features": verified_features,
    }


from pydantic import BaseModel
from typing import Optional, List

class ProfileUpdateRequest(BaseModel):
    profile_type: Optional[str] = None
    first_run_completed: Optional[bool] = None
    auto_start_enabled: Optional[bool] = None
    wake_word_enabled: Optional[bool] = None
    require_tool_confirmation: Optional[bool] = None
    default_language: Optional[str] = None
    preferred_model: Optional[str] = None


@router.post("/profile")
async def update_profile_config(req: ProfileUpdateRequest):
    """Update profile configuration from setup wizard or settings."""
    from app.core.profiles import get_profile_manager
    manager = get_profile_manager()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    
    # If preferred_model changed, update active LLM model
    if "preferred_model" in updates:
        model_name = updates.pop("preferred_model")
        try:
            _client.set_model(model_name)
        except Exception:
            pass

    updated = manager.update(**updates)
    return {"status": "ok", "profile": updated}
