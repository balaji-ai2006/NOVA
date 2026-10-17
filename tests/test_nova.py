"""
NOVA Test Suite — Core Unit Tests
----------------------------------
Run with:  pytest tests/ -v

Tests cover:
  - Memory store CRUD
  - Config defaults
  - OllamaClient status (mocked)
  - Vision fallback
  - Tools allowlist enforcement

Note: Tests that require Ollama running are skipped automatically
      when Ollama is offline (marked with pytest.mark.integration).
"""

import pytest
import tempfile
from pathlib import Path
import sys

# Ensure project root is on path when running pytest from project dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ────────────────────────────── Config tests ──────────────────────────── #

class TestConfig:
    def test_app_name(self):
        from app.core.config import APP_NAME
        assert APP_NAME == "NOVA"

    def test_app_version_format(self):
        from app.core.config import APP_VERSION
        parts = APP_VERSION.split(".")
        assert len(parts) == 3, "Version should be X.Y.Z"

    def test_default_model_set(self):
        from app.core.config import DEFAULT_LLM_MODEL
        assert isinstance(DEFAULT_LLM_MODEL, str)
        assert len(DEFAULT_LLM_MODEL) > 0

    def test_memory_db_path_is_path(self):
        from app.core.config import MEMORY_DB_PATH
        assert isinstance(MEMORY_DB_PATH, Path)

    def test_telemetry_is_disabled(self):
        from app.core.config import TELEMETRY
        assert TELEMETRY is False, "Telemetry MUST always be off"

    def test_allowed_apps_has_entries(self):
        from app.core.config import ALLOWED_APPS
        assert isinstance(ALLOWED_APPS, dict)
        assert len(ALLOWED_APPS) > 0


# ────────────────────────────── Memory tests ──────────────────────────── #

class TestMemoryStore:
    """Test the SQLite memory store with a temporary in-memory DB."""

    @pytest.fixture
    def store(self):
        """
        Create a fresh MemoryStore backed by a temp file.
        On Windows, SQLite keeps the file locked until all connections close.
        We explicitly close any open connection before unlinking.
        """
        import sqlite3
        from app.memory.store import MemoryStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp = Path(f.name)
        s = MemoryStore(db_path=tmp)
        yield s
        # Close any lingering SQLite connection then delete
        try:
            conn = sqlite3.connect(str(tmp))
            conn.close()
        except Exception:
            pass
        import gc; gc.collect()   # force garbage collection to release file handles
        tmp.unlink(missing_ok=True)

    def test_save_and_list(self, store):
        store.save("Remember my name is Balaji")
        items = store.list_all()
        assert len(items) == 1
        assert items[0]["content"] == "Remember my name is Balaji"

    def test_save_multiple(self, store):
        store.save("Fact 1")
        store.save("Fact 2")
        store.save("Fact 3")
        assert len(store.list_all()) == 3

    def test_delete(self, store):
        mem_id = store.save("To be deleted")
        assert store.delete(mem_id) is True
        assert len(store.list_all()) == 0

    def test_delete_nonexistent(self, store):
        assert store.delete(9999) is False

    def test_clear_all(self, store):
        store.save("A")
        store.save("B")
        count = store.clear_all()
        assert count == 2
        assert store.list_all() == []

    def test_search(self, store):
        store.save("Python is great")
        store.save("I love coffee")
        results = store.search("python")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    def test_context_string_empty(self, store):
        assert store.as_context_string() == ""

    def test_context_string_with_data(self, store):
        store.save("My favourite colour is blue")
        ctx = store.as_context_string()
        assert "blue" in ctx
        assert "Memories" in ctx

    def test_tags_saved(self, store):
        store.save("Birthday is in January", tags="personal,dates")
        items = store.list_all()
        assert items[0]["tags"] == "personal,dates"

    def test_sensitive_info_rejected(self, store):
        with pytest.raises(ValueError, match="Sensitive information"):
            store.save("my password is: SuperSecret12345!")

    def test_retrieve_relevant(self, store):
        store.save("I love reading science fiction books", tags="reading")
        store.save("My Python project is named NOVA", tags="coding")
        store.save("I enjoy drinking green tea in the morning", tags="drink")

        # Query about python
        relevant = store.retrieve_relevant("How do I run my Python project?")
        assert len(relevant) > 0
        assert "Python" in relevant[0]["content"]


# ────────────────────────────── Speech & Text tests ───────────────────── #

class TestSpeechSanitizer:
    def test_clean_text_for_speech_removes_code_blocks(self):
        from app.voice.tts import clean_text_for_speech
        raw = "Here is the code:\n```python\nprint('hello')\n```\nIt works!"
        cleaned = clean_text_for_speech(raw)
        assert "print('hello')" not in cleaned
        assert "Code block omitted" in cleaned
        assert "Here is the code" in cleaned

    def test_clean_text_for_speech_removes_markdown_formatting(self):
        from app.voice.tts import clean_text_for_speech
        raw = "## Welcome to **NOVA**!\n- Fast\n- *Offline*\nCheck [Link](https://example.com) 😊"
        cleaned = clean_text_for_speech(raw)
        assert "**" not in cleaned
        assert "##" not in cleaned
        assert "https://" not in cleaned
        assert "Welcome to NOVA" in cleaned
        assert "Fast" in cleaned

    def test_system_prompt_multilingual(self):
        from app.brain.prompts import get_system_prompt
        prompt = get_system_prompt()
        assert "Marathi" in prompt
        assert "Hindi" in prompt
        assert "मराठी" in prompt
        assert "हिन्दी" in prompt

    def test_response_language_stays_english_by_default(self):
        from app.brain.prompts import get_system_prompt
        prompt = get_system_prompt()
        assert "ENGLISH (DEFAULT)" in prompt
        prompt_en = get_system_prompt(response_language="en")
        assert "ENGLISH (DEFAULT)" in prompt_en

    def test_manual_language_override_marathi(self):
        from app.brain.prompts import get_system_prompt
        prompt_mr = get_system_prompt(response_language="mr")
        assert "MARATHI" in prompt_mr
        assert "मराठी" in prompt_mr

    def test_manual_language_override_hindi(self):
        from app.brain.prompts import get_system_prompt
        prompt_hi = get_system_prompt(response_language="hi")
        assert "HINDI" in prompt_hi
        assert "हिन्दी" in prompt_hi



# ────────────────────────────── OllamaClient tests ────────────────────── #

class TestOllamaClient:
    """Unit tests for OllamaClient that don't require Ollama running."""

    def test_pull_instructions_contains_model(self):
        from app.brain.ollama_client import OllamaClient
        client = OllamaClient(model="llama3.2:3b")
        instructions = client.pull_instructions()
        assert "llama3.2:3b" in instructions
        assert "ollama pull" in instructions

    def test_clear_history(self):
        from app.brain.ollama_client import OllamaClient, Message
        client = OllamaClient()
        # Manually inject history
        client._history = [
            Message(role="user",      content="hi"),
            Message(role="assistant", content="hello"),
        ]
        client.clear_history()
        assert client.get_history() == []

    def test_set_model(self):
        from app.brain.ollama_client import OllamaClient
        client = OllamaClient(model="llama3.2:3b")
        client.set_model("phi3:mini")
        assert client.model == "phi3:mini"

    def test_status_offline(self):
        """Status check when Ollama is not running should not raise."""
        from app.brain.ollama_client import OllamaClient
        # Use a port that is definitely not Ollama
        client = OllamaClient(base_url="http://localhost:19999")
        status = client.get_status()
        assert status.ollama_running is False
        assert status.error is not None


# ────────────────────────────── Vision tests ──────────────────────────── #

class TestVision:
    def test_basic_analysis_returns_string(self):
        """basic_image_analysis should return a label string, not crash."""
        from app.vision.camera import basic_image_analysis
        import numpy as np, cv2
        # Create a tiny 10x10 blue image
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        img[:, :] = (255, 0, 0)   # BGR blue
        _, buf = cv2.imencode(".jpg", img)
        result = basic_image_analysis(bytes(buf))
        assert "[Basic analysis" in result

    def test_basic_analysis_handles_bad_input(self):
        from app.vision.camera import basic_image_analysis
        result = basic_image_analysis(b"not an image")
        assert "Basic analysis" in result


# ────────────────────────────── Tools tests ──────────────────────────── #

class TestComputerTools:
    def test_open_app_not_in_allowlist(self):
        from app.tools.computer import open_application
        with pytest.raises(ValueError, match="not in the allowed"):
            open_application("malware.exe")

    def test_read_file_nonexistent(self):
        from app.tools.computer import read_file
        with pytest.raises(RuntimeError, match="not found"):
            read_file("/nonexistent/path/file.txt")

    def test_read_file_forbidden_extension(self):
        import tempfile, os
        from app.tools.computer import read_file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"fake")
            fpath = f.name
        try:
            with pytest.raises(ValueError, match="not in the allowed list"):
                read_file(fpath)
        finally:
            os.unlink(fpath)

    def test_read_file_content(self):
        import tempfile, os
        from app.tools.computer import read_file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("Hello, NOVA!")
            fpath = f.name
        try:
            content = read_file(fpath)
            assert "Hello, NOVA!" in content
        finally:
            os.unlink(fpath)

    def test_system_info_keys(self):
        from app.tools.computer import get_system_info
        info = get_system_info()
        # Should have these keys or an error key
        if "error" not in info:
            assert "cpu_percent" in info
            assert "ram_total_gb" in info
