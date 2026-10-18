"""
NOVA Voice Assistant Daemon — Continuous Background Listener
-----------------------------------------------------------
Listens continuously via the microphone.
When the wake word "Nova" (or "Hey Nova") is detected:
1. Acknowledges with voice / chime ("Yes Balaji?" / "Yes?")
2. Transcribes the user's spoken command using faster-whisper
3. Executes automations (YouTube, Chrome, Memory, Apps)
4. Or queries the local LLM and speaks the answer out loud using TTS
"""

import sys
import time
import math
import wave
import tempfile
import threading
import numpy as np
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sounddevice as sd

from app.core.logger import get_logger
from app.voice.stt import get_stt
from app.voice.tts import get_tts
from app.tools.automations import handle_intent
from app.memory.store import MemoryStore
from app.brain.ollama_client import OllamaClient

logger = get_logger("voice_daemon")


class VoiceDaemon:
    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.025,
        silence_duration: float = 0.65,
        max_recording_duration: float = 10.0,
    ):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.silence_duration = silence_duration
        self.max_recording_duration = max_recording_duration

        self.stt = get_stt()
        self.tts = get_tts()
        self.tts.enabled = True  # Ensure voice assistant speaks back!
        self.memory = MemoryStore()
        self.client = OllamaClient()

        self._running = False
        self._user_name: Optional[str] = None
        self._load_user_name()

    def _load_user_name(self) -> None:
        """Fetch saved user name from long-term memory."""
        try:
            memories = self.memory.list_all()
            for m in memories:
                content = m.get("content", "")
                if "name is" in content.lower():
                    # e.g. "User's name is Balaji."
                    parts = content.split("name is")
                    if len(parts) > 1:
                        self._user_name = parts[1].strip().rstrip(".")
                        break
        except Exception:
            pass

    def speak(self, text: str, block: bool = True) -> None:
        """Speak out text to the user via TTS."""
        if not text:
            return
        logger.info("NOVA Speaking: %s", text)
        try:
            self.tts.clean_and_speak(text, block=block)
        except Exception as e:
            logger.error("TTS speaking error: %s", e)

    def _is_wake_word(self, text: str) -> tuple[bool, str]:
        """
        Check if text contains wake words like "nova", "hey nova", "नोव्हा".
        Returns (has_wake_word, remaining_command).
        """
        lower = text.lower().strip()
        wake_words = [
            "hey nova", "ok nova", "hi nova", "hello nova", "nova",
            "नोव्हा", "नवा", "नोवा", "नव्हा",
            "nowa", "nowha", "lua", "noah", "no va", "noba", "lova", "noha"
        ]

        for w in wake_words:
            if lower.startswith(w):
                remainder = lower[len(w):].strip(" ,.:;!?")
                return True, remainder
            elif w in lower:
                # Word anywhere in query
                idx = lower.find(w)
                remainder = (lower[:idx] + " " + lower[idx + len(w):]).strip(" ,.:;!?")
                return True, remainder

        return False, ""

    def record_phrase(self) -> Optional[np.ndarray]:
        """
        Record audio dynamically until silence is detected.
        Uses RMS energy to detect start and end of speech.
        """
        chunk_size = int(self.sample_rate * 0.1)  # 100ms chunks
        buffer = []
        is_speaking = False
        silence_start = None
        start_time = time.time()

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32") as stream:
                while self._running:
                    chunk, _ = stream.read(chunk_size)
                    chunk = chunk.flatten()
                    rms = np.sqrt(np.mean(chunk**2))

                    if rms > self.energy_threshold:
                        if not is_speaking:
                            is_speaking = True
                            logger.info("Speech detected, recording...")
                        silence_start = None
                        buffer.append(chunk)
                    elif is_speaking:
                        buffer.append(chunk)
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= self.silence_duration:
                            logger.info("Silence detected. Finished recording phrase.")
                            break

                    # Max safety duration
                    if is_speaking and (time.time() - start_time >= self.max_recording_duration):
                        logger.info("Max phrase duration reached.")
                        break

                    time.sleep(0.01)

            if buffer and is_speaking:
                audio = np.concatenate(buffer)
                # Filter out extremely short accidental clicks (< 0.5s)
                if len(audio) >= self.sample_rate * 0.5:
                    return audio

        except Exception as e:
            logger.error("Microphone recording error: %s", e)

        return None

    def audio_to_wav_file(self, audio_data: np.ndarray) -> Path:
        """Convert float32 numpy array to a temp 16-bit PCM WAV file."""
        # Convert float32 [-1.0, 1.0] to int16
        audio_int16 = (audio_data * 32767).astype(np.int16)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        return tmp_path

    def process_command(self, command: str) -> None:
        """
        Execute command via automations (YouTube, Chrome, Apps, Identity)
        or via local LLM.
        """
        logger.info("Processing command: '%s'", command)

        # 1. Check direct automations (YouTube, Chrome, Memory, Apps)
        is_action, reply = handle_intent(command)
        if is_action:
            self._load_user_name()
            self.speak(reply)
            return

        # 2. General LLM query
        logger.info("Sending query to LLM...")
        name_str = f"User is {self._user_name}. " if self._user_name else ""
        try:
            extra_ctx = self.memory.as_context_string(query=command) or None
            # If Ollama is available, stream answer
            tokens = []
            for token in self.client.chat(
                user_message=command,
                extra_context=(name_str + (extra_ctx or "")).strip() or None,
                response_language="auto",
            ):
                tokens.append(token)

            full_reply = "".join(tokens).strip()
            if full_reply:
                self.speak(full_reply)
            else:
                self.speak("Kahi samasya aali, punha sanga.")
        except Exception as e:
            logger.error("LLM execution error: %s", e)
            self.speak("Ollama connect zala nahi. Krupaya Ollama suru ahe ka te paha.")

    def run(self) -> None:
        """Main daemon loop."""
        self._running = True
        logger.info("=" * 60)
        logger.info("  NOVA Voice Assistant Daemon is RUNNING")
        logger.info("  Say 'Nova' or 'Hey Nova' to activate!")
        logger.info("=" * 60)

        # Greet user if name known
        greeting = f"नमस्कार {self._user_name}! नोव्हा सुरू झाले आहे, बोला." if self._user_name else "नमस्कार! नोव्हा सुरू झाले आहे, बोला."
        self.speak(greeting)

        while self._running:
            try:
                audio = self.record_phrase()
                if audio is None:
                    continue

                # Transcribe
                wav_path = self.audio_to_wav_file(audio)
                try:
                    transcription = self.stt.transcribe_file(wav_path)
                finally:
                    wav_path.unlink(missing_ok=True)

                if not transcription or not transcription.strip():
                    continue

                logger.info("Heard: '%s'", transcription)

                # 1. Direct automation match (YouTube, Chrome, Apps, Identity, etc.)
                is_action, reply = handle_intent(transcription)
                if is_action:
                    self._load_user_name()
                    logger.info("Direct command recognized: %s", reply)
                    self.speak(reply)
                    continue

                # 2. Wake-word check
                has_wake, cmd = self._is_wake_word(transcription)
                if has_wake:
                    logger.info("Wake word detected! Command: '%s'", cmd)
                    if cmd and len(cmd) > 1:
                        # Direct command: "Nova, play song on youtube"
                        self.process_command(cmd)
                    else:
                        # Just wake word: "Nova"
                        ack = f"हो {self._user_name}! मी ऐकते आहे, बोला." if self._user_name else "हो! मी ऐकते आहे, बोला."
                        self.speak(ack)

                        # Listen for follow-up command
                        followup_audio = self.record_phrase()
                        if followup_audio is not None:
                            fwav = self.audio_to_wav_file(followup_audio)
                            try:
                                follow_cmd = self.stt.transcribe_file(fwav)
                            finally:
                                fwav.unlink(missing_ok=True)

                            if follow_cmd and follow_cmd.strip():
                                self.process_command(follow_cmd)

            except KeyboardInterrupt:
                logger.info("Voice daemon stopped by user.")
                break
            except Exception as e:
                logger.error("Error in voice daemon loop: %s", e)
                time.sleep(1)


def start_daemon_background():
    """Start VoiceDaemon in a background daemon thread."""
    daemon = VoiceDaemon()
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    return daemon


if __name__ == "__main__":
    daemon = VoiceDaemon()
    daemon.run()
