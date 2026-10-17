"""
Load .env file at startup if present.
This file is imported by app/main.py before any config is read.

Place a .env file in the project root (copy from .env.example).
The .env file is listed in .gitignore and will never be committed.
"""

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[NOVA] Loaded environment from {env_path}")
else:
    print("[NOVA] No .env file found — using defaults and OS environment variables.")
