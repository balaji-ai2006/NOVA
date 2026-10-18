"""
NOVA Windows Auto-Start Setup
------------------------------
Sets up or removes NOVA from Windows Startup folder so NOVA starts automatically
every time the laptop boots or the user logs in.

Usage:
    python scripts/setup_autostart.py --enable   # Enable auto-start on boot
    python scripts/setup_autostart.py --disable  # Disable auto-start
    python scripts/setup_autostart.py --status   # Check status
"""

import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SILENT_VBS = PROJECT_ROOT / "start_silent.vbs"
STARTUP_DIR = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
SHORTCUT_PATH = STARTUP_DIR / "NOVA_AI_Assistant.bat"


def get_status() -> bool:
    """Return True if autostart file exists in Windows Startup."""
    return SHORTCUT_PATH.exists()


def enable_autostart() -> None:
    """Create startup runner in Windows Startup directory."""
    if not SILENT_VBS.exists():
        print(f"Error: {SILENT_VBS} not found!")
        sys.exit(1)

    STARTUP_DIR.mkdir(parents=True, exist_ok=True)

    # We write a tiny launcher bat in the Startup folder that calls wscript start_silent.vbs
    bat_content = f'@echo off\nwscript.exe "{SILENT_VBS}"\n'
    SHORTCUT_PATH.write_text(bat_content, encoding="utf-8")
    print("=" * 60)
    print(" [OK] NOVA Auto-Start is now ENABLED!")
    print(f" Location: {SHORTCUT_PATH}")
    print(" NOVA will start automatically whenever you turn on your laptop.")
    print("=" * 60)


def disable_autostart() -> None:
    """Remove startup runner from Windows Startup directory."""
    if SHORTCUT_PATH.exists():
        SHORTCUT_PATH.unlink()
        print("=" * 60)
        print(" [OK] NOVA Auto-Start is now DISABLED.")
        print("=" * 60)
    else:
        print("Auto-start was not enabled.")


def main():
    parser = argparse.ArgumentParser(description="Configure NOVA Windows Auto-Start")
    parser.add_argument("--enable", action="store_true", help="Enable auto-start on boot")
    parser.add_argument("--disable", action="store_true", help="Disable auto-start")
    parser.add_argument("--status", action="store_true", help="Check current auto-start status")

    args = parser.parse_args()

    if args.enable:
        enable_autostart()
    elif args.disable:
        disable_autostart()
    elif args.status:
        enabled = get_status()
        status_text = "ENABLED (Auto-starts on boot)" if enabled else "DISABLED"
        print(f"NOVA Auto-Start Status: {status_text}")
    else:
        # Default interactive behavior if no flags
        enabled = get_status()
        print(f"Current status: {'ENABLED' if enabled else 'DISABLED'}")
        ans = input("Do you want to ENABLE NOVA auto-start on laptop boot? (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            enable_autostart()
        else:
            print("No changes made.")


if __name__ == "__main__":
    main()
