"""
NOVA FastAPI Integration Tests
-------------------------------
Run with:  pytest tests/test_api.py -v

Tests the HTTP API endpoints using FastAPI's TestClient (synchronous).
These tests do NOT require Ollama to be running:
- Chat endpoints return 500/error when Ollama is offline (tested gracefully)
- Memory, Status, Tools endpoints are tested fully
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def client():
    """Provide a FastAPI TestClient for the whole test module."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestStatusAPI:
    def test_status_endpoint_reachable(self, client):
        r = client.get("/api/status/")
        assert r.status_code == 200
        data = r.json()
        assert "app" in data
        assert "llm" in data
        assert data["app"]["name"] == "NOVA"

    def test_system_status(self, client):
        r = client.get("/api/status/system")
        assert r.status_code == 200

    def test_ollama_status(self, client):
        r = client.get("/api/status/ollama")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data


class TestMemoryAPI:
    def test_list_memories_empty(self, client):
        # Clear first to ensure clean state
        client.delete("/api/memory/")
        r = client.get("/api/memory/")
        assert r.status_code == 200
        assert r.json()["memories"] == []

    def test_save_memory(self, client):
        r = client.post("/api/memory/save", json={"content": "Test memory", "tags": "test"})
        assert r.status_code == 200
        assert r.json()["status"] == "saved"
        assert "id" in r.json()

    def test_save_empty_memory_rejected(self, client):
        r = client.post("/api/memory/save", json={"content": "   "})
        assert r.status_code == 400

    def test_delete_memory(self, client):
        r = client.post("/api/memory/save", json={"content": "Delete me"})
        mem_id = r.json()["id"]
        d = client.delete(f"/api/memory/{mem_id}")
        assert d.status_code == 200
        assert d.json()["status"] == "deleted"

    def test_delete_nonexistent(self, client):
        r = client.delete("/api/memory/999999")
        assert r.status_code == 404

    def test_clear_memories(self, client):
        client.post("/api/memory/save", json={"content": "One"})
        client.post("/api/memory/save", json={"content": "Two"})
        r = client.delete("/api/memory/")
        assert r.status_code == 200

    def test_memory_context(self, client):
        client.post("/api/memory/save", json={"content": "NOVA is cool"})
        r = client.get("/api/memory/context")
        assert r.status_code == 200
        assert "context" in r.json()


class TestToolsAPI:
    def test_allowed_apps_list(self, client):
        r = client.get("/api/tools/allowed-apps")
        assert r.status_code == 200
        assert "allowed" in r.json()
        assert isinstance(r.json()["allowed"], list)

    def test_open_invalid_app(self, client):
        r = client.post("/api/tools/open-app", json={"app_name": "virus.exe"})
        assert r.status_code == 400

    def test_read_nonexistent_file(self, client):
        r = client.post("/api/tools/read-file", json={"file_path": "/no/such/file.txt"})
        assert r.status_code == 400

    def test_system_info(self, client):
        r = client.get("/api/tools/system-info")
        assert r.status_code == 200


class TestVoiceAPI:
    def test_voice_status(self, client):
        r = client.get("/api/voice/status")
        assert r.status_code == 200
        data = r.json()
        assert "stt" in data
        assert "tts" in data

    def test_tts_stop(self, client):
        r = client.post("/api/voice/tts/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_tts_clean(self, client):
        r = client.post("/api/voice/tts/clean", json={"text": "Hello **world**! ```code```"})
        assert r.status_code == 200
        assert "**" not in r.json()["cleaned"]

    def test_transcribe_auto_language_payload(self, client):
        # Generate dummy 1-second silence WAV
        import io, wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        buf.seek(0)

        # Post with language="auto"
        r = client.post(
            "/api/voice/transcribe?language=auto",
            files={"file": ("test.wav", buf.getvalue(), "audio/wav")}
        )
        assert r.status_code == 200
        data = r.json()
        assert "transcription" in data
        assert "detected_language" in data
        assert "confidence" in data
        assert data["is_auto"] is True

    def test_transcribe_explicit_language_payload(self, client):
        import io, wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        buf.seek(0)

        r = client.post(
            "/api/voice/transcribe?language=en",
            files={"file": ("test.wav", buf.getvalue(), "audio/wav")}
        )
        assert r.status_code == 200
        data = r.json()
        assert "transcription" in data
        assert data["is_auto"] is False


class TestVisionAPI:
    def test_vision_status(self, client):
        r = client.get("/api/vision/status")
        assert r.status_code == 200
        data = r.json()
        assert "camera_available" in data
        assert "vision_model" in data


class TestChatAPI:
    def test_clear_chat(self, client):
        r = client.post("/api/chat/clear", json={"session_id": "session_test"})
        assert r.status_code == 200
        assert r.json()["session_id"] == "session_test"

    def test_get_history_empty_after_clear(self, client):
        client.post("/api/chat/clear", json={"session_id": "session_test"})
        r = client.get("/api/chat/history?session_id=session_test")
        assert r.status_code == 200
        data = r.json()
        assert "history" in data
        assert data["session_id"] == "session_test"
        assert isinstance(data["history"], list)

    def test_send_empty_message_rejected(self, client):
        r = client.post("/api/chat/send", json={"message": "  "})
        assert r.status_code == 400

    def test_switch_to_nonexistent_model(self, client):
        r = client.post("/api/chat/model", json={"model": "fakegpt:99b"})
        # Should fail because model doesn't exist in Ollama
        assert r.status_code in (404, 503)


class TestUI:
    def test_root_serves_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "NOVA" in r.text
        assert "text/html" in r.headers.get("content-type", "")

    def test_static_css_served(self, client):
        r = client.get("/static/css/nova.css")
        assert r.status_code == 200

    def test_static_js_served(self, client):
        r = client.get("/static/js/nova.js")
        assert r.status_code == 200
