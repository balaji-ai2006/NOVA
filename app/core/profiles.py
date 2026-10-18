"""
NOVA Edition Profiles
----------------------
Supports two operational modes with a single shared codebase:
1. Personal Profile:
   - For developer / personal laptop (Balaji)
   - Auto-start enabled
   - Background wake-word detection active
   - Direct approved computer automation
   - Persistent personal memory
2. Universal Profile:
   - For distributing to other Windows users
   - Safe defaults: First-run setup wizard enabled
   - Wake-word and auto-start require explicit user opt-in
   - Tool confirmation required for system actions
   - Clean slate: no pre-existing chat history or personal data
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from app.core.paths import APP_CONFIG_DIR

PROFILE_FILE = APP_CONFIG_DIR / "profile_config.json"


@dataclass
class ProfileConfig:
    profile_type: str = "personal"  # "personal" or "universal"
    app_name: str = "NOVA"
    version: str = "0.1.0"
    first_run_completed: bool = False
    auto_start_enabled: bool = False
    wake_word_enabled: bool = False
    require_tool_confirmation: bool = True
    online_services_allowed: bool = False
    allowed_apps: Optional[list[str]] = None
    default_language: str = "en"
    telemetry_enabled: bool = False  # Always False for privacy


def get_default_profile(profile_type: str = "personal") -> ProfileConfig:
    """Return profile configuration defaults based on edition type."""
    p_type = profile_type.lower().strip()
    if p_type == "universal":
        return ProfileConfig(
            profile_type="universal",
            app_name="NOVA",
            version="0.1.0",
            first_run_completed=False,
            auto_start_enabled=False,
            wake_word_enabled=False,
            require_tool_confirmation=True,
            online_services_allowed=False,
            allowed_apps=["notepad", "calculator", "explorer", "browser"],
            default_language="en",
            telemetry_enabled=False,
        )
    # Default to personal profile
    return ProfileConfig(
        profile_type="personal",
        app_name="NOVA",
        version="0.1.0",
        first_run_completed=True,
        auto_start_enabled=True,
        wake_word_enabled=True,
        require_tool_confirmation=False,
        online_services_allowed=True,
        allowed_apps=["notepad", "calculator", "explorer", "browser", "chrome"],
        default_language="en",
        telemetry_enabled=False,
    )


class ProfileManager:
    """Manages reading, caching, and updating active profile configuration."""

    def __init__(self, config_path: Path = PROFILE_FILE):
        self.config_path = config_path
        self._config = self._load()

    def _load(self) -> ProfileConfig:
        env_profile = os.getenv("NOVA_PROFILE")
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                # If environment variable overrides profile type, respect it
                if env_profile and env_profile.lower() != data.get("profile_type"):
                    data["profile_type"] = env_profile.lower()
                return ProfileConfig(**data)
            except Exception:
                pass

        # If no config on disk, create based on env or default to personal
        initial_type = env_profile or "personal"
        profile = get_default_profile(initial_type)
        self.save(profile)
        return profile

    def get_config(self) -> ProfileConfig:
        return self._config

    def save(self, config: Optional[ProfileConfig] = None) -> None:
        if config is not None:
            self._config = config
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(asdict(self._config), indent=2),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> ProfileConfig:
        current = asdict(self._config)
        for k, v in kwargs.items():
            if k in current:
                current[k] = v
        self._config = ProfileConfig(**current)
        self.save()
        return self._config


_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
