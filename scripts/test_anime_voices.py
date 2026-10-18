import asyncio
import edge_tts
import soundfile as sf
import sounddevice as sd
import os

candidates = [
    ("en-US-AvaMultilingualNeural", "+20Hz", "+6%", "ava_18yo.mp3"),
    ("en-US-EmmaMultilingualNeural", "+22Hz", "+8%", "emma_18yo.mp3"),
    ("en-US-JennyNeural", "+18Hz", "+6%", "jenny_18yo.mp3"),
    ("en-US-AriaNeural", "+20Hz", "+6%", "aria_18yo.mp3"),
]

async def test_voices():
    os.makedirs("data/audio_tests", exist_ok=True)
    text = "Hello Balaji! I'm Nova, your anime companion. How can I help you today?"
    for voice, pitch, rate, filename in candidates:
        filepath = os.path.join("data/audio_tests", filename)
        comm = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
        await comm.save(filepath)
        size = os.path.getsize(filepath)
        print(f"Generated {voice} -> {size} bytes")

asyncio.run(test_voices())
