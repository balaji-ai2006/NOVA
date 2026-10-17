#!/usr/bin/env python3
"""
scripts/pull_model.py — Interactive model downloader for NOVA
-------------------------------------------------------------
Run this script to pull the recommended model for your hardware.

Usage:  python scripts/pull_model.py
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

MODELS = {
    "1": ("llama3.2:3b",    "~2 GB",  "Recommended for RTX 3050 6GB — great quality/speed balance"),
    "2": ("llama3.2:1b",    "~1.3 GB","Fastest, for weak hardware or CPU-only"),
    "3": ("llama3.1:8b",    "~5 GB",  "Better reasoning, needs 8+ GB VRAM"),
    "4": ("phi3:mini",      "~2.3 GB","Microsoft Phi-3 — good on CPU"),
    "5": ("moondream",      "~1.8 GB","Vision LLM — for image understanding (optional)"),
    "6": ("codellama:7b",   "~4 GB",  "For coding tasks — needs 8 GB VRAM"),
}

def main():
    print("\n╔═══════════════════════════════════════════╗")
    print("║        NOVA — Model Downloader            ║")
    print("╚═══════════════════════════════════════════╝\n")
    print("Choose a model to download (Internet required for this step):\n")

    for key, (name, size, desc) in MODELS.items():
        print(f"  [{key}] {name:<22} {size:<10} {desc}")

    print("\n  [q] Quit\n")
    choice = input("Enter choice: ").strip().lower()

    if choice == "q":
        sys.exit(0)

    if choice not in MODELS:
        print("Invalid choice.")
        sys.exit(1)

    model_name, size, desc = MODELS[choice]
    print(f"\nPulling {model_name} ({size})…")
    print("This may take a while depending on your internet speed.\n")

    try:
        result = subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"\n✅ {model_name} downloaded successfully!")
        print(f"Set NOVA_LLM_MODEL={model_name} in your .env file.")
    except subprocess.CalledProcessError:
        print(f"\n❌ Failed to pull {model_name}.")
        print("Make sure Ollama is installed: https://ollama.com/download")
    except FileNotFoundError:
        print("\n❌ 'ollama' command not found.")
        print("Install Ollama from: https://ollama.com/download")


if __name__ == "__main__":
    main()
