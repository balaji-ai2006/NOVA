#!/usr/bin/env python3
"""
scripts/check_system.py — NOVA Pre-flight System Check
-------------------------------------------------------
Run this script BEFORE starting NOVA to verify everything is configured.

Usage:  python scripts/check_system.py
"""

import sys
import subprocess
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = "✅"
WARN = "⚠️ "
FAIL = "❌"
INFO = "ℹ️ "


def section(title: str):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print('─' * 50)


def check(label: str, ok: bool, message: str = "", warn_not_fail: bool = False):
    icon = PASS if ok else (WARN if warn_not_fail else FAIL)
    print(f"  {icon}  {label}")
    if message:
        print(f"       {message}")


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║       NOVA — System Pre-flight Check         ║")
    print("╚══════════════════════════════════════════════╝")

    # ── Python version
    section("Python")
    major, minor = sys.version_info.major, sys.version_info.minor
    ok = (major == 3 and minor >= 11)
    check(f"Python {major}.{minor}", ok,
          "" if ok else "NOVA requires Python 3.11+. Download from python.org")

    # ── Core packages
    section("Core Dependencies")
    packages = {
        "fastapi":              "FastAPI web framework",
        "uvicorn":              "ASGI server",
        "httpx":                "HTTP client (Ollama API)",
        "python_multipart":     "File upload support",
        "psutil":               "System resource monitoring",
        "dotenv":               "Environment configuration",
        "cv2":                  "OpenCV (camera capture)",
    }
    for pkg, desc in packages.items():
        try:
            __import__(pkg)
            check(f"{pkg} — {desc}", True)
        except ImportError:
            check(f"{pkg} — {desc}", False, f"pip install {pkg.replace('_', '-')}")

    # ── Optional packages
    section("Optional Dependencies")
    optional = {
        "faster_whisper": "Offline speech-to-text",
        "pyttsx3":        "Offline text-to-speech",
        "pyaudio":        "Microphone recording",
    }
    for pkg, desc in optional.items():
        try:
            __import__(pkg)
            check(f"{pkg} — {desc}", True)
        except ImportError:
            check(f"{pkg} — {desc}", False, f"Optional: pip install {pkg.replace('_', '-')}", warn_not_fail=True)

    # ── Ollama
    section("Ollama (Local AI)")
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        check("Ollama server", True)
        if models:
            check(f"Models available: {', '.join(models)}", True)
        else:
            check("Local models", False,
                  "No models found!\nRun: ollama pull llama3.2:3b", warn_not_fail=True)
    except Exception:
        check("Ollama server", False,
              "Ollama is not running.\n"
              "       Start it: ollama serve\n"
              "       Install:  https://ollama.com/download")

    # ── Camera
    section("Camera / Vision")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened()
        cap.release()
        check("Webcam index 0", ok,
              "" if ok else "No webcam detected or in use by another app.")
    except ImportError:
        check("OpenCV", False, "pip install opencv-python-headless")

    # ── GPU
    section("GPU (NVIDIA)")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip()
            check(f"NVIDIA GPU: {gpu_info}", True,
                  "GPU acceleration available for faster-whisper (set NOVA_STT_DEVICE=cuda)")
        else:
            check("NVIDIA GPU", False, "Not detected (CPU inference will be used)", warn_not_fail=True)
    except Exception:
        check("nvidia-smi", False, "Not found (CPU inference will be used)", warn_not_fail=True)

    # ── Environment file
    section("Configuration")
    env_path = Path(__file__).parent.parent / ".env"
    check(".env file",
          env_path.exists(),
          "" if env_path.exists() else "Copy .env.example to .env and edit as needed",
          warn_not_fail=not env_path.exists())

    print(f"\n{'═' * 50}")
    print("  Pre-flight check complete.")
    print("  Start NOVA:   python main.py")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
