"""
NOVA Path Management & Isolation
--------------------------------
Handles path resolution for development, portable, and distributable packaged builds.
Ensures user data, configurations, and logs are cleanly isolated:
- Packaged / Installed mode: Uses %LOCALAPPDATA%/NOVA/
- Development / Portable mode: Uses local project root or custom override
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Detect runtime environment
# ---------------------------------------------------------------------------
IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

if IS_FROZEN:
    # Running inside a PyInstaller bundle
    BUNDLE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    EXE_DIR = Path(sys.executable).resolve().parent
    PROJECT_ROOT = EXE_DIR
else:
    # Running from source in repo
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    BUNDLE_DIR = PROJECT_ROOT

# Check if portable mode is forced
PORTABLE_MODE = os.getenv("NOVA_PORTABLE_MODE", "false").lower() in ("true", "1")

# ---------------------------------------------------------------------------
# User Data & Storage Paths
# ---------------------------------------------------------------------------
if PORTABLE_MODE or not IS_FROZEN:
    # In dev or portable mode, store in project root data/ if desired,
    # or fallback to local appdata if user specifies
    APP_DATA_DIR = PROJECT_ROOT / "data"
    APP_CONFIG_DIR = PROJECT_ROOT / "data" / "config"
    APP_LOG_DIR = PROJECT_ROOT / "logs"
else:
    # Distributable Windows Standard: %LOCALAPPDATA%/NOVA
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data) / "NOVA"
    else:
        base_dir = Path.home() / ".nova"

    APP_DATA_DIR = base_dir / "data"
    APP_CONFIG_DIR = base_dir / "config"
    APP_LOG_DIR = base_dir / "logs"

DB_DIR = APP_DATA_DIR / "databases"
MODELS_DIR = APP_DATA_DIR / "models"
UI_DIR = BUNDLE_DIR / "ui"

# Ensure all critical user directories exist
for directory in (APP_DATA_DIR, APP_CONFIG_DIR, APP_LOG_DIR, DB_DIR, MODELS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
