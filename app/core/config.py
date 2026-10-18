"""
NOVA Core Configuration
-----------------------
Centralised settings for the whole NOVA assistant.
All tuneable knobs live here so nothing is hard-coded in individual modules.
"""

import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project & Data Paths (Supports Dev, Portable, and Frozen Packaged builds)
# ---------------------------------------------------------------------------
from app.core.paths import (
    PROJECT_ROOT,
    APP_DATA_DIR as DATA_DIR,
    DB_DIR,
    MODELS_DIR,
    APP_LOG_DIR as LOG_DIR,
    UI_DIR,
    IS_FROZEN,
)

# ---------------------------------------------------------------------------
# Application Metadata
# ---------------------------------------------------------------------------
APP_NAME    = "NOVA"
APP_VERSION = "0.1.0"
APP_TAGLINE = "Personal Offline-First Multimodal AI Assistant"

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.getenv("NOVA_HOST", "127.0.0.1")
PORT = int(os.getenv("NOVA_PORT", "7860"))

# ---------------------------------------------------------------------------
# Ollama / Local LLM
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Default model: llama3.2:3b is a great fit for 16 GB RAM / 6 GB VRAM.
# The user can override by setting NOVA_LLM_MODEL in their .env file.
DEFAULT_LLM_MODEL = os.getenv("NOVA_LLM_MODEL", "llama3.2:3b")
LLM_TIMEOUT       = int(os.getenv("NOVA_LLM_TIMEOUT", "120"))  # seconds
LLM_STREAM        = os.getenv("NOVA_LLM_STREAM", "true").lower() == "true"
LLM_MAX_TOKENS    = int(os.getenv("NOVA_LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE   = float(os.getenv("NOVA_LLM_TEMPERATURE", "0.7"))

# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------
# moondream2 is tiny (~1.8 GB) and runs well on 6 GB VRAM
VISION_MODEL          = os.getenv("NOVA_VISION_MODEL", "moondream")
VISION_ENABLED        = os.getenv("NOVA_VISION_ENABLED", "true").lower() == "true"
CAMERA_INDEX          = int(os.getenv("NOVA_CAMERA_INDEX", "0"))

# ---------------------------------------------------------------------------
# Voice (Speech-to-Text)
# ---------------------------------------------------------------------------
STT_ENGINE       = os.getenv("NOVA_STT_ENGINE", "faster-whisper")  # or "vosk"
STT_MODEL        = os.getenv("NOVA_STT_MODEL", "base")             # tiny/base/small
STT_LANGUAGE     = os.getenv("NOVA_STT_LANGUAGE", "auto")          # auto/en/hi/mr
STT_DEVICE       = os.getenv("NOVA_STT_DEVICE", "auto")            # auto/cpu/cuda

# ---------------------------------------------------------------------------
# Voice (Text-to-Speech)
# ---------------------------------------------------------------------------
TTS_ENGINE       = os.getenv("NOVA_TTS_ENGINE", "pyttsx3")         # pyttsx3 or piper
TTS_ENABLED      = os.getenv("NOVA_TTS_ENABLED", "true").lower() == "true"
TTS_RATE         = int(os.getenv("NOVA_TTS_RATE", "175"))           # words per minute
TTS_VOLUME       = float(os.getenv("NOVA_TTS_VOLUME", "0.9"))
PIPER_DIR        = MODELS_DIR / "piper"
PIPER_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
MEMORY_DB_PATH   = DB_DIR / "nova_memory.db"
MEMORY_ENABLED   = os.getenv("NOVA_MEMORY_ENABLED", "true").lower() == "true"
SHORT_TERM_TURNS = int(os.getenv("NOVA_SHORT_TERM_TURNS", "20"))    # messages kept in context

# ---------------------------------------------------------------------------
# Privacy / Offline
# ---------------------------------------------------------------------------
OFFLINE_MODE     = os.getenv("NOVA_OFFLINE_MODE", "true").lower() == "true"
TELEMETRY        = False  # NEVER enabled — hard-coded off

# ---------------------------------------------------------------------------
# Computer Tools
# ---------------------------------------------------------------------------
# Allowlisted app names → executable paths or just names for subprocess
ALLOWED_APPS: dict[str, str] = {
    "notepad":    "notepad.exe",
    "calculator": "calc.exe",
    "explorer":   "explorer.exe",
    "browser":    "start",    # uses shell start command
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("NOVA_LOG_LEVEL", "INFO")
LOG_FILE  = LOG_DIR / "nova.log"
