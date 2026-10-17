"""
NOVA Computer Tools — Safe, Allowlisted System Actions
-------------------------------------------------------
NOVA can perform a small set of pre-approved computer actions.
The user is ALWAYS asked for confirmation before anything runs.

Security model:
  - All allowed actions are listed in ALLOWED_APPS (config.py).
  - Shell commands are NEVER generated and executed automatically.
  - File reads require user-provided paths; no directory traversal.
  - File writes require explicit user approval at the API level.
  - Nothing in this module starts background recording.

Adding new actions:
  1. Add the name to ALLOWED_APPS in config.py.
  2. Add the handler below.
  3. Document the action in README.md.
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional

from app.core.config import ALLOWED_APPS
from app.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Application launcher
# ---------------------------------------------------------------------------

def open_application(app_name: str) -> str:
    """
    Open a pre-approved application by name.

    Parameters
    ----------
    app_name : Must be a key in ALLOWED_APPS (case-insensitive).

    Returns
    -------
    Status string shown to the user.

    Raises
    ------
    ValueError if app_name is not in the allowlist.
    """
    key = app_name.lower().strip()
    if key not in ALLOWED_APPS:
        allowed = ", ".join(ALLOWED_APPS.keys())
        raise ValueError(
            f"'{app_name}' is not in the allowed applications list.\n"
            f"Allowed: {allowed}"
        )

    exe = ALLOWED_APPS[key]
    logger.info("Opening allowed app: %s (%s)", key, exe)

    try:
        if platform.system() == "Windows":
            if exe == "start":
                subprocess.Popen(["cmd", "/c", "start", ""], shell=False)
            else:
                subprocess.Popen([exe], shell=False)
        else:
            # Linux / macOS (Raspberry Pi path)
            subprocess.Popen([exe])
        return f"✅ Opened {app_name}."
    except FileNotFoundError:
        return f"❌ Could not find '{exe}'. Is it installed?"
    except Exception as exc:
        return f"❌ Error opening {app_name}: {exc}"


# ---------------------------------------------------------------------------
# File reader
# ---------------------------------------------------------------------------

def read_file(file_path: str, max_chars: int = 4000) -> str:
    """
    Read and return text content from a user-specified file.

    Only reads files the user explicitly provides (no crawling).
    Truncates at max_chars to avoid flooding the context window.

    Parameters
    ----------
    file_path : Absolute or relative path provided by the user.
    max_chars : Maximum characters to return.

    Returns
    -------
    File content string.

    Raises
    ------
    ValueError for unsafe paths, RuntimeError for read errors.
    """
    path = Path(file_path).resolve()

    # Basic safety: refuse paths that look like system directories
    forbidden_roots = [
        Path("C:/Windows"),
        Path("C:/System32"),
        Path("/etc"),
        Path("/sys"),
        Path("/proc"),
    ]
    for bad in forbidden_roots:
        try:
            path.relative_to(bad)
            raise ValueError(f"Reading from '{bad}' is not allowed for safety.")
        except ValueError as e:
            if "not allowed" in str(e):
                raise

    if not path.exists():
        raise RuntimeError(f"File not found: {path}")
    if not path.is_file():
        raise RuntimeError(f"'{path}' is not a file.")

    # Only allow text-like extensions
    allowed_ext = {
        ".txt", ".md", ".py", ".js", ".ts", ".html", ".css",
        ".json", ".yaml", ".yml", ".csv", ".log", ".ini", ".cfg", ".toml",
    }
    if path.suffix.lower() not in allowed_ext:
        raise ValueError(
            f"File type '{path.suffix}' is not in the allowed list for reading.\n"
            f"Allowed: {', '.join(sorted(allowed_ext))}"
        )

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Could not read file: {exc}")

    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[… truncated at {max_chars} characters]"

    logger.info("File read: %s (%d chars)", path.name, len(content))
    return content


# ---------------------------------------------------------------------------
# System information (safe, read-only)
# ---------------------------------------------------------------------------

def get_system_info() -> dict:
    """
    Return safe, non-sensitive system information.
    Used by the dashboard status panel.
    """
    import psutil
    import platform

    try:
        mem   = psutil.virtual_memory()
        disk  = psutil.disk_usage("/")
        cpu_p = psutil.cpu_percent(interval=0.3)
        return {
            "os":          platform.system(),
            "os_version":  platform.version()[:60],
            "python":      platform.python_version(),
            "cpu_percent": cpu_p,
            "ram_total_gb":  round(mem.total / 1e9, 1),
            "ram_used_gb":   round(mem.used  / 1e9, 1),
            "ram_percent":   mem.percent,
            "disk_total_gb": round(disk.total / 1e9, 1),
            "disk_free_gb":  round(disk.free  / 1e9, 1),
        }
    except ImportError:
        return {"error": "psutil not installed — run: pip install psutil"}
    except Exception as exc:
        return {"error": str(exc)}
