"""
Tests for NOVA Stage 1:
- Path Isolation (Dev vs Packaged)
- Profile System (Personal vs Universal Editions)
- Hardware Compatibility & Recommendation Engine
- About & Verified Features API
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.paths import PROJECT_ROOT, APP_DATA_DIR, DB_DIR, MODELS_DIR
from app.core.profiles import get_default_profile, ProfileManager, ProfileConfig
from app.core.hardware import get_hardware_profile


def test_paths_integrity():
    """Verify that all core directories are properly resolved and exist."""
    assert PROJECT_ROOT.exists()
    assert APP_DATA_DIR.exists()
    assert DB_DIR.exists()
    assert MODELS_DIR.exists()


def test_profile_presets():
    """Test Personal and Universal profile presets."""
    personal = get_default_profile("personal")
    assert personal.profile_type == "personal"
    assert personal.auto_start_enabled is True
    assert personal.wake_word_enabled is True
    assert personal.require_tool_confirmation is False

    universal = get_default_profile("universal")
    assert universal.profile_type == "universal"
    assert universal.auto_start_enabled is False
    assert universal.wake_word_enabled is False
    assert universal.require_tool_confirmation is True
    assert universal.first_run_completed is False


def test_profile_manager_update(tmp_path: Path):
    """Test updating profile parameters."""
    cfg_file = tmp_path / "test_profile.json"
    mgr = ProfileManager(config_path=cfg_file)

    cfg = mgr.get_config()
    assert cfg.profile_type in ("personal", "universal")

    updated = mgr.update(first_run_completed=True, default_language="en")
    assert updated.first_run_completed is True
    assert updated.default_language == "en"

    # Reload from disk to verify persistence
    mgr2 = ProfileManager(config_path=cfg_file)
    assert mgr2.get_config().first_run_completed is True


def test_hardware_detection_and_recommendations():
    """Verify hardware profile detection produces valid tiers and recommendations."""
    hw = get_hardware_profile()
    assert hw.os_name in ("Windows", "Linux", "Darwin")
    assert hw.cpu_cores_logical >= 1
    assert hw.ram_total_gb > 0
    assert hw.hardware_tier in ("entry", "balanced", "high_performance")
    assert hw.recommended_llm in ("llama3.2:1b", "llama3.2:3b", "llama3.1:8b")


def test_about_endpoint_contract():
    """Test /api/status/about returns required semantic versioning and verified features."""
    client = TestClient(app)
    res = client.get("/api/status/about")
    assert res.status_code == 200

    data = res.json()
    # 1. Product & Versioning
    assert data["product"]["name"] == "NOVA"
    assert data["product"]["version"] == "0.1.0"
    assert data["product"]["distributable_ready"] is False  # Must not claim public ready yet

    # 2. Hardware specs
    assert "hardware" in data
    assert "hardware_tier" in data["hardware"]

    # 3. Verified features table
    features = data["verified_features"]
    assert "speech_to_text" in features
    assert "text_to_speech" in features
    assert "computer_automations" in features
    assert "local_llm_inference" in features

    # Verified features rule: only True if verified
    for key, feat in features.items():
        assert "name" in feat
        assert "implemented" in feat
        assert "verified" in feat
        assert isinstance(feat["verified"], bool)


def test_profile_update_endpoint():
    """Test updating profile via POST /api/status/profile."""
    client = TestClient(app)
    res = client.post(
        "/api/status/profile",
        json={
            "first_run_completed": True,
            "require_tool_confirmation": True,
            "wake_word_enabled": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["profile"]["first_run_completed"] is True
    assert data["profile"]["require_tool_confirmation"] is True
