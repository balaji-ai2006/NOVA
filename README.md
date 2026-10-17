# NOVA — Personal Offline-First Multimodal AI Assistant

> **"Your own Project Astra — running 100% on your laptop."**

NOVA is a free, open-source, offline-first personal AI assistant with voice, vision, memory, and safe computer tools — all running locally on your machine using [Ollama](https://ollama.com/).

---

## Table of Contents

1. [What NOVA Does](#1-what-nova-does)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Prerequisites](#3-prerequisites)
4. [Windows Installation](#4-windows-installation)
5. [Downloading a Model](#5-downloading-a-model)
6. [Running NOVA](#6-running-nova)
7. [Running Tests](#7-running-tests)
8. [Enabling Voice & Vision](#8-enabling-voice--vision)
9. [Full Offline Operation](#9-full-offline-operation)
10. [Common Errors & Fixes](#10-common-errors--fixes)
11. [Raspberry Pi Migration Guide](#11-raspberry-pi-migration-guide)
12. [Feature Roadmap](#12-feature-roadmap)
13. [Privacy Policy](#13-privacy-policy)
14. [Project Structure](#14-project-structure)

---

## 1. What NOVA Does

| Feature | Description |
|---|---|
| **Local Chat** | Streams answers from a local LLM via Ollama. No cloud needed after setup. |
| **Voice Input** | Push-to-talk speech recognition via faster-whisper (Whisper distilled). |
| **Voice Output** | Offline TTS using the OS's built-in speech engine (SAPI5 on Windows). |
| **Vision** | Webcam capture + local vision model (moondream) for image Q&A. |
| **Memory** | Short-term context + SQLite long-term memory you explicitly approve. |
| **Computer Tools** | Safely opens allowlisted apps, reads selected files, reports system status. |
| **Dashboard** | Dark futuristic UI with live status, model selector, memory panel. |
| **Privacy** | 100% local. No telemetry. No background recording. |

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────┐
│  Browser  (http://localhost:7860)                              │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────────────┐   │
│  │  Chat UI     │  │ Voice UI   │  │  Vision / Camera UI  │   │
│  └──────┬───────┘  └─────┬──────┘  └──────────┬───────────┘   │
└─────────┼────────────────┼────────────────────┼───────────────┘
          │ SSE / HTTP     │ WAV upload          │ HTTP
┌─────────▼────────────────▼────────────────────▼───────────────┐
│  FastAPI Backend  (app/main.py)                                │
│  ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ /api/chat  │ │ /api/voice   │ │/api/vision │ │/api/mem  │  │
│  └─────┬──────┘ └──────┬───────┘ └─────┬──────┘ └────┬─────┘  │
└────────┼───────────────┼───────────────┼──────────────┼────────┘
         │               │               │              │
┌────────▼──┐   ┌────────▼──┐   ┌────────▼──┐   ┌─────▼──────┐
│  Ollama   │   │ faster-   │   │ OpenCV    │   │  SQLite    │
│  LLM API  │   │ whisper   │   │ webcam +  │   │  Memory    │
│  :11434   │   │ (offline) │   │ moondream │   │  Database  │
└───────────┘   └───────────┘   └───────────┘   └────────────┘
```

**Data never leaves your machine.**  
The only time network is used is the initial `pip install` and `ollama pull` (one-time model downloads).

---

## 3. Prerequisites

| Requirement | Notes |
|---|---|
| **Windows 10/11** (64-bit) | macOS/Linux also work with minor changes |
| **Python 3.11+** | You have 3.13 — ✅ |
| **Ollama** | Free, open-source local LLM runtime |
| **~4 GB free disk** | For `llama3.2:3b` model |
| **GPU** (optional but recommended) | RTX 3050 6GB — ✅ great for Ollama + moondream |
| **Microphone** (optional) | For voice input |
| **Webcam** (optional) | For vision features |

---

## 4. Windows Installation

### Step 1: Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/NOVA.git
cd NOVA
```

### Step 2: Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

> 💡 You'll see `(.venv)` in your prompt when the environment is active.

### Step 3: Install Python dependencies

```powershell
pip install -r requirements.txt
```

This installs FastAPI, Ollama client, faster-whisper, pyttsx3, OpenCV, and more.  
**No large model files are downloaded** — only code libraries.

### Step 4: Install Ollama

Download from **https://ollama.com/download** and run the installer.  
After installing, verify with:

```powershell
ollama --version
```

### Step 5: Copy the environment file

```powershell
copy .env.example .env
```

Edit `.env` to customise the model or ports if needed.

---

## 5. Downloading a Model

You need **internet only for this step**. After download, NOVA runs completely offline.

### Recommended for your RTX 3050 6GB:

```powershell
# Chat LLM — fits in 6 GB VRAM with room to spare
ollama pull llama3.2:3b    # ~2 GB download

# Vision LLM (optional) — for image Q&A
ollama pull moondream      # ~1.8 GB download
```

### Interactive model chooser:

```powershell
python scripts/pull_model.py
```

### Model size guide:

| Model | VRAM needed | Download size | Quality |
|---|---|---|---|
| `llama3.2:1b` | ~1 GB | 1.3 GB | Basic |
| `llama3.2:3b` | ~3 GB | 2 GB | ⭐ **Recommended** |
| `llama3.1:8b` | ~6 GB | 5 GB | Great |
| `phi3:mini` | ~2 GB | 2.3 GB | CPU-friendly |
| `moondream` | ~2 GB | 1.8 GB | Vision only |

---

## 6. Running NOVA

### Start the Ollama server (required — keep this terminal open):

```powershell
ollama serve
```

### Start NOVA (open a second terminal):

```powershell
# Activate your virtualenv first
.venv\Scripts\activate

# Launch NOVA (opens browser automatically)
python main.py
```

NOVA will open at **http://localhost:7860**

### Development mode (auto-reload on file changes):

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 7860 --reload
```

### System pre-flight check:

```powershell
python scripts/check_system.py
```

---

## 7. Running Tests

```powershell
# Unit tests (no Ollama needed)
python -m pytest tests/test_nova.py -v

# API integration tests (no Ollama needed)
python -m pytest tests/test_api.py -v

# All tests
python -m pytest tests/ -v

# With coverage report
pip install pytest-cov
python -m pytest tests/ --cov=app --cov-report=term-missing
```

**Current test results:** 26/26 unit tests pass + full API test suite.

---

## 8. Enabling Voice & Vision

### Voice Input (Speech-to-Text)

NOVA uses **faster-whisper** (already installed). On first use it downloads the Whisper `base` model (~145 MB) to `~/.cache/huggingface/`.

1. Click and **hold the microphone button** to record.
2. Release to transcribe and auto-send.

To use CUDA acceleration for faster transcription:
```
# In .env:
NOVA_STT_DEVICE=cuda
```

> ⚠️ CUDA STT requires CUDA Toolkit 11.8 + cuDNN 8 to be installed.

### Microphone (PyAudio — optional for browser recording)

Browser-based recording works out of the box (uses WebRTC). If you want server-side mic access:

```powershell
pip install pyaudio
# If that fails on Windows:
pip install pipwin && pipwin install pyaudio
```

### Voice Output (Text-to-Speech)

pyttsx3 is already installed. Enable in the UI via the **🔊 Voice** button or in `.env`:

```
NOVA_TTS_ENABLED=true
```

### Vision (Camera + Image Understanding)

1. Make sure no other app is using your webcam.
2. Click the **📷 camera button** in NOVA's UI.
3. For real image understanding, pull moondream:
   ```powershell
   ollama pull moondream
   ```
4. Without moondream, NOVA shows a clearly labelled "basic analysis" using pixel statistics — it **never pretends** to understand an image it hasn't actually processed.

---

## 9. Full Offline Operation

After completing the steps above **once** (with internet), NOVA works fully offline:

| Component | Offline? | Notes |
|---|---|---|
| Chat (LLM) | ✅ | Ollama + local model |
| Voice Input | ✅ | faster-whisper (cached locally) |
| Voice Output | ✅ | pyttsx3 uses OS TTS |
| Vision (camera) | ✅ | OpenCV is local |
| Vision (understanding) | ✅ | moondream runs via Ollama |
| Memory | ✅ | SQLite, 100% local |
| Computer Tools | ✅ | Local OS calls |
| Fonts | ⚠️ | Google Fonts loaded on first visit; cached by browser |

**To use completely offline:** Start `ollama serve` and `python main.py`. That's it.

---

## 10. Common Errors & Fixes

### "Ollama is not running"
```
Error: connect ECONNREFUSED 127.0.0.1:11434
```
**Fix:** Run `ollama serve` in a separate terminal and leave it open.

---

### "No local models found"
```
RuntimeError: No local models found.
```
**Fix:** `ollama pull llama3.2:3b` (requires internet, one time only).

---

### "Camera index 0 could not be opened"
**Fixes:**
- Close Skype, Teams, or any app using the camera.
- Try `NOVA_CAMERA_INDEX=1` in `.env` if you have multiple cameras.

---

### pyttsx3 init error on Windows
**Fix:** Install `pywin32`: `pip install pywin32`

---

### faster-whisper CUDA error
**Fix:** Either set `NOVA_STT_DEVICE=cpu` in `.env`, or install CUDA Toolkit 11.8 + cuDNN 8.

---

### Port 7860 already in use ([Errno 10048])
```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 7860): [winerror 10048] only one usage of each socket address is normally permitted
```
**Fix:** Another NOVA or uvicorn instance is already running in the background.
1. Find and close the existing instance:
   ```powershell
   Get-Process python* | Stop-Process -Force
   ```
2. Or change the port in `.env`:
   ```
   NOVA_PORT=7861
   ```

---

### "open() got an unexpected keyword argument 'metadata_errors'"
**Cause:** In `av` (PyAV) version 19+, the deprecated `metadata_errors` argument was removed, while `faster-whisper` still specifies it.
**Fix:** NOVA includes an automatic built-in compatibility patch in `app/voice/stt.py` that intercepts calls to `av.open` and strips the unsupported keyword argument seamlessly.

---

### "UnicodeEncodeError: 'charmap' codec can't encode characters"
**Cause:** Default Windows PowerShell / CMD uses `cp1252` encoding which cannot display Devanagari (Marathi/Hindi) or unicode symbols.
**Fix:** NOVA automatically reconfigures `sys.stdout` to UTF-8 at startup and uses ASCII-safe logs for system redirection.

---

### Multilingual Support (Marathi, Hindi, English)
NOVA is natively equipped to converse in Marathi (मराठी), Hindi (हिन्दी), and English:
- **Text Chat:** Simply write in Marathi, Hindi, or Hinglish/Marathish. NOVA detects your language and replies in the same tongue.
- **Voice Input:** Whisper STT auto-detects spoken languages by default (`NOVA_STT_LANGUAGE=auto`). You can also lock it to Marathi (`mr`), Hindi (`hi`), or English (`en`) in the Settings modal.
- **Voice Output:** NOVA's text sanitizer automatically removes code blocks, markdown symbols, and URLs before synthesis so spoken Marathi, Hindi, and English sound clean and natural.

---

### Voice Controls & Hands-Free Mode
- **🔊 Voice Toggle:** Turns spoken responses on or off.
- **⏹ Stop Speaking:** Appears dynamically while speech is playing. Clicking it silences the voice immediately.
- **🎙 Hands-Free Mode:** When active, NOVA automatically listens for your next voice question as soon as it finishes answering. You can disable it at any time with 1 click.

---

## 11. Raspberry Pi Migration Guide

NOVA is designed to be portable. Here's the migration path:

### What works identically on Pi:
- FastAPI backend
- SQLite memory
- Ollama (if installed on Pi — see note)
- Memory and tools modules

### What needs changes on Pi:

| Component | Pi Setup |
|---|---|
| **Ollama** | Ollama runs on Pi 4/5 (ARM). Install from https://ollama.com/download. Use tiny models (`llama3.2:1b`). |
| **faster-whisper** | Works on Pi (slow). Set `NOVA_STT_MODEL=tiny` and `NOVA_STT_DEVICE=cpu`. |
| **pyttsx3** | Needs espeak: `sudo apt install espeak python3-espeak` |
| **OpenCV** | `pip install opencv-python` (not headless) or `sudo apt install python3-opencv` |
| **Camera** | Pi Camera Module: use `libcamera` or `picamera2` instead of OpenCV (planned feature) |
| **GPU acceleration** | Not available on Pi — all CPU. Use tiny/1b models. |

### Pi-specific .env settings:
```
NOVA_LLM_MODEL=llama3.2:1b
NOVA_STT_MODEL=tiny
NOVA_STT_DEVICE=cpu
NOVA_CAMERA_INDEX=0
```

---

## 12. Feature Roadmap

### ✅ Implemented
- [x] FastAPI backend with all API routes
- [x] Streaming chat via Ollama SSE
- [x] Dark futuristic UI with real-time status
- [x] Short-term conversational memory
- [x] Long-term SQLite memory (save/view/delete/clear)
- [x] Webcam capture
- [x] Vision LLM via moondream (Ollama)
- [x] Basic OpenCV fallback analysis (clearly labelled)
- [x] Offline STT via faster-whisper
- [x] Browser-based push-to-talk voice recording
- [x] Offline TTS via pyttsx3
- [x] Safe computer tools (app launcher, file reader)
- [x] System resource monitoring (CPU/RAM)
- [x] Model switcher in UI
- [x] Settings modal
- [x] Privacy mode indicator
- [x] Pre-flight system check script
- [x] Interactive model downloader script
- [x] 26 passing unit tests + API integration tests
- [x] .env configuration system
- [x] Proper .gitignore

### 🧪 Experimental
- [ ] CUDA-accelerated STT (needs cuDNN setup)
- [ ] Server-side microphone recording (PyAudio)
- [ ] Vision + chat integration (analyse image then continue conversation)

### 📋 Planned
- [ ] Pi Camera Module support (picamera2)
- [ ] Wake word detection ("Hey NOVA")
- [ ] Better Markdown rendering in chat
- [ ] Export chat history to PDF/text
- [ ] Plugin system for custom tools
- [ ] RAG (Retrieval Augmented Generation) from local documents
- [ ] Multiple conversation sessions
- [ ] Mobile-responsive UI improvements
- [ ] Kokoro TTS for higher quality voice (optional model download)

---

## 13. Privacy Policy

NOVA is designed with privacy-first principles:

- **No telemetry** — `TELEMETRY = False` is hard-coded in `app/core/config.py`.
- **No cloud AI** — all inference runs locally via Ollama.
- **Camera is explicit** — only activated when you click the camera button.
- **Microphone is explicit** — browser asks for permission; only records when button held.
- **No background recording** — voice and video are not stored.
- **Memory is opt-in** — nothing is automatically remembered without your action.
- **Memory stays local** — stored in `data/databases/nova_memory.db` only.
- **The only network calls are:**
  - `pip install` (one-time setup)
  - `ollama pull <model>` (one-time model download)
  - Google Fonts CDN on first UI load (cached by browser)

---

## 14. Project Structure

```
NOVA/
├── app/
│   ├── main.py                  # FastAPI application factory
│   ├── core/
│   │   ├── config.py            # All settings — edit here first
│   │   ├── logger.py            # Shared logger (file + console)
│   │   └── env_loader.py        # Loads .env file
│   ├── api/
│   │   ├── chat.py              # POST /api/chat/send (SSE streaming)
│   │   ├── voice.py             # POST /api/voice/transcribe
│   │   ├── vision.py            # POST /api/vision/capture, /analyse
│   │   ├── memory.py            # CRUD /api/memory/
│   │   ├── tools.py             # POST /api/tools/open-app
│   │   └── status.py            # GET  /api/status/
│   ├── brain/
│   │   └── ollama_client.py     # Ollama LLM wrapper with streaming
│   ├── voice/
│   │   ├── stt.py               # faster-whisper speech-to-text
│   │   └── tts.py               # pyttsx3 text-to-speech
│   ├── vision/
│   │   └── camera.py            # Webcam + moondream vision LLM
│   ├── memory/
│   │   └── store.py             # SQLite memory CRUD
│   └── tools/
│       └── computer.py          # App launcher, file reader, sysinfo
├── ui/
│   ├── templates/
│   │   └── index.html           # Main UI HTML
│   └── static/
│       ├── css/nova.css         # Dark futuristic design system
│       └── js/nova.js           # Frontend logic (chat, voice, vision)
├── tests/
│   ├── test_nova.py             # 26 unit tests (config, memory, tools, vision)
│   └── test_api.py              # API integration tests
├── scripts/
│   ├── check_system.py          # Pre-flight system check
│   └── pull_model.py            # Interactive model downloader
├── data/
│   ├── databases/               # nova_memory.db (git-ignored)
│   └── models/                  # Reserved for future local model files
├── docs/                        # Additional documentation
├── logs/                        # nova.log (git-ignored)
├── main.py                      # Root launcher (python main.py)
├── requirements.txt             # Python dependencies
├── .env.example                 # Config template
├── .gitignore                   # Excludes .venv, .env, data, logs
└── README.md                    # This file
```

---

## Quick Start (TL;DR)

```powershell
# 1. Install Ollama from https://ollama.com/download
# 2. Pull a model (internet required, one-time):
ollama pull llama3.2:3b

# 3. Install Python deps:
pip install -r requirements.txt

# 4. Copy config:
copy .env.example .env

# 5. Start Ollama server (keep open):
ollama serve

# 6. In a new terminal, start NOVA:
python main.py
# → Opens http://localhost:7860 automatically
```

**Total disk space:** ~2-5 GB (model files) + ~200 MB (Python packages)  
**After initial setup:** 100% offline. Zero ongoing costs.

---

*NOVA is inspired by Google Project Astra. Built with ❤️ using open-source software.*
