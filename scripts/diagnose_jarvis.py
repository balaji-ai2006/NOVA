import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("       NOVA JARVIS-MODE FULL SYSTEM DIAGNOSTICS")
print("=" * 60)

print("\n[1] WINDOWS AUTO-START ON BOOT")
from scripts.setup_autostart import get_status, SHORTCUT_PATH, SILENT_VBS
print(f" - Startup Shortcut File: {SHORTCUT_PATH}")
print(f" - Exists: {SHORTCUT_PATH.exists()}")
print(f" - Silent VBS Launcher: {SILENT_VBS} (Exists: {SILENT_VBS.exists()})")
print(f" - Auto-Start Status: {'[PASS] ENABLED' if get_status() else '[FAIL] DISABLED'}")

print("\n[2] USER MEMORY & PROFILE")
from app.memory.store import MemoryStore
m = MemoryStore()
memories = m.list_all()
print(f" - Total Memories Stored: {len(memories)}")
found_name = None
for mem in memories:
    content = mem.get("content", "")
    if "name is" in content.lower():
        found_name = content
        print(f" - Saved Identity: {content}")
        break
if not found_name:
    print(" - [WARN] Name not found in memories.")

print("\n[3] MICROPHONE & VOICE ENGINE (STT & TTS)")
import sounddevice as sd
from app.voice.stt import get_stt
from app.voice.tts import get_tts

stt = get_stt()
tts = get_tts()
input_device = sd.query_devices(kind="input")
print(f" - Microphone Device: {input_device.get('name')}")
print(f" - STT Model: faster-whisper ({stt.model_size}) on {stt.device} [Available: {stt.is_available()}]")
print(f" - TTS Engine: {tts._engine_type} [Available: {tts.is_available()}, Enabled: {tts.enabled}]")

print("\n[4] CONTINUOUS VOICE DAEMON & WAKE-WORD ('Nova')")
from app.voice.listener import VoiceDaemon
vd = VoiceDaemon()
print(f" - Daemon Loaded: YES")
print(f" - User Name in Daemon: {vd._user_name}")

test_phrases = [
    ("Nova, open chrome", True, "open chrome"),
    ("Hey Nova, youtube var Shivaji Maharaj song lav", True, "youtube var shivaji maharaj song lav"),
    ("Nova", True, ""),
    ("just testing without wake word", False, ""),
]
print(" - Testing Wake-Word Parser:")
for phrase, exp_wake, exp_cmd in test_phrases:
    has_wake, cmd = vd._is_wake_word(phrase)
    status = "[PASS]" if has_wake == exp_wake else "[FAIL]"
    print(f"    {status} '{phrase}' -> Wake: {has_wake}, Cmd: '{cmd}'")

print("\n[5] AUTOMATIONS & ACTIONS (YouTube, Chrome, Apps, Identity)")
from app.tools.automations import handle_intent

automation_tests = [
    ("Nova me Balaji ahe", "Identity Save"),
    ("me kon ahe", "Identity Recall"),
    ("Nova youtube var Shivba song lav", "YouTube Play"),
    ("Nova google var Mumbai weather search kar", "Google Search"),
    ("Nova open notepad", "App Launch (Notepad)"),
    ("Nova open calculator", "App Launch (Calculator)"),
    ("Nova open chrome", "Browser Launch"),
]
for cmd, desc in automation_tests:
    ok, reply = handle_intent(cmd)
    status = "[PASS]" if ok else "[FAIL]"
    print(f" - {status} [{desc}] -> Query: '{cmd}'")
    print(f"     Reply: {reply}")

print("\n[6] HARDWARE & LOCAL AI STATUS")
from app.core.hardware import get_hardware_profile
from app.brain.ollama_client import OllamaClient
hw = get_hardware_profile()
print(f" - CPU: {hw.cpu_cores_logical} cores | RAM: {hw.ram_total_gb} GB")
print(f" - GPU: {hw.gpu_name} ({hw.vram_mb} MB VRAM)")
print(f" - Hardware Tier: {hw.hardware_tier.upper()}")
print(f" - Recommended LLM: {hw.recommended_llm}")

client = OllamaClient()
status = client.get_status()
print(f" - Ollama Running: {status.ollama_running}")
print(f" - Installed Local Models: {status.available_models}")

print("\n" + "=" * 60)
print(" DIAGNOSTICS COMPLETED")
print("=" * 60)
