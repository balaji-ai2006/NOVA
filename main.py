"""
NOVA — Root Launcher
--------------------
Run this file to start NOVA:

    python main.py

Or with auto-reload (development):

    uvicorn app.main:app --host 127.0.0.1 --port 7860 --reload

Then open http://localhost:7860 in your browser.
"""

import sys
import subprocess
import webbrowser
import threading
import time
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports work
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import HOST, PORT
from app.core.logger import get_logger

logger = get_logger("launcher")


def open_browser_after_delay(url: str, delay: float = 2.0):
    """Open the browser after a short delay to let the server start."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    url = f"http://{HOST}:{PORT}"
    logger.info("Starting NOVA at %s", url)
    open_browser_after_delay(url)

    # Start Background Voice Assistant Daemon ("Nova" wake-word listener)
    try:
        from app.voice.listener import start_daemon_background
        logger.info("Starting background Voice Daemon (continuous 'Nova' listener)...")
        start_daemon_background()
    except Exception as exc:
        logger.warning("Could not start background voice daemon: %s", exc)

    try:
        import uvicorn
    except ImportError:
        logger.error(
            "uvicorn is not installed.\n"
            "Run:  pip install uvicorn\n"
            "Or install all deps:  pip install -r requirements.txt"
        )
        sys.exit(1)

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        # reload=True,   # Uncomment during development
    )


if __name__ == "__main__":
    main()
