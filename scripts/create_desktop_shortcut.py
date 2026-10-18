"""
Creates a desktop shortcut to NOVA on the user's Windows Desktop.
"""

import os
from pathlib import Path

desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
project_root = Path(__file__).resolve().parent.parent
vbs_path = project_root / "start_silent.vbs"

shortcut_path = desktop / "NOVA AI Assistant.bat"
content = f'@echo off\nwscript.exe "{vbs_path}"\n'

try:
    shortcut_path.write_text(content, encoding="utf-8")
    print(f"[OK] Desktop shortcut created at: {shortcut_path}")
except Exception as e:
    print(f"Error creating desktop shortcut: {e}")
