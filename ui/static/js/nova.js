/**
 * NOVA — Shadow Monarch AI System Frontend Logic
 * ──────────────────────────────────────────────
 * Multilingual offline multimodal AI assistant.
 * Handles:
 *   - Multilingual acoustic speech-to-text (Whisper auto-detect English/Marathi/Hindi)
 *   - User review & edit dock before sending voice transcriptions
 *   - Response language control (English by default, separate from STT language)
 *   - Solo Leveling inspired HUD navigation and holographic panels
 *   - Fast SSE streaming chat with local Ollama LLMs
 *   - Push-to-talk & hands-free continuous voice interaction
 *   - Offline TTS speech synthesis with Devanagari phonetics
 *   - Computer vision webcam capture & analysis
 *   - SQLite long-term memory vault
 *   - System resource monitoring & diagnostics
 */

/* ─────────────────────────────── State ─────────────── */
const state = {
  sessionId:             'session_' + Date.now(),
  isGenerating:          false,
  isRecording:           false,
  isSpeaking:            false,
  ttsEnabled:            false,
  handsFree:             false,
  memoryEnabled:         true,
  responseLanguage:      'en',    // Default: English (independent of STT)
  sttLanguage:           'auto',  // Default: Auto Detect (Whisper acoustic detection)
  autoSendVoice:         false,   // Default: false (allows user to review/edit before sending)
  currentModel:          '',
  visionCapture:         null,
  mediaRecorder:         null,
  mediaStream:           null,
  audioChunks:           [],
  speechReviewTimer:     null,
  pollingTimer:          null,
};

/* ─────────────────────────────── DOM refs ──────────── */
const $ = (id) => document.getElementById(id);

// Chat & Layout
const chatArea            = $('chatArea');
const messages            = $('messages');
const welcomeScreen       = $('welcomeScreen');
const chatInput           = $('chatInput');
const btnSend             = $('btnSend');
const btnMic              = $('btnMic');
const btnCamera           = $('btnCamera');
const btnClear            = $('btnClear');
const sidebarToggle       = $('sidebarToggle');
const sidebar             = $('sidebar');

// Top-bar Controls
const btnStopTTS          = $('btnStopTTS');
const btnHandsFree        = $('btnHandsFree');
const btnSTTIndicator     = $('btnSTTIndicator');
const btnLangToggle       = $('btnLangToggle');
const btnTTS              = $('btnTTS');
const btnOffline          = $('btnOffline');
const btnSettings         = $('btnSettings');

// Navigation Tabs
const navChat             = $('navChat');
const navMemory           = $('navMemory');
const navVoice            = $('navVoice');
const navVision           = $('navVision');
const navTools            = $('navTools');
const navSettings         = $('navSettings');

// Speech Review Dock (Requirement 9)
const speechReviewDock    = $('speechReviewDock');
const speechDetectedTag   = $('speechDetectedTag');
const speechConfidenceTag = $('speechConfidenceTag');
const speechReviewText    = $('speechReviewText');
const btnConfirmSendVoice = $('btnConfirmSendVoice');
const btnEditVoiceInput   = $('btnEditVoiceInput');
const btnCancelVoiceReview= $('btnCancelVoiceReview');

// Live Voice Pill
const voiceStatusPill     = $('voiceStatusPill');
const voiceStatusText     = $('voiceStatusText');
const btnCancelVoice      = $('btnCancelVoice');

// Vision Preview
const visionPreview       = $('visionPreview');
const visionImg           = $('visionImg');
const visionAnswer        = $('visionAnswer');
const visionQuestion      = $('visionQuestion');
const btnAnalyse          = $('btnAnalyse');
const btnCloseVision      = $('btnCloseVision');

// Memory
const memorySection       = $('memorySection');
const memoryList          = $('memoryList');
const memoryInput         = $('memoryInput');
const btnSaveMemory       = $('btnSaveMemory');
const btnClearMemory      = $('btnClearMemory');

// Models
const modelList           = $('modelList');
const modelSelect         = $('modelSelect');
const btnApplyModel       = $('btnApplyModel');

// Settings Modal
const settingsOverlay     = $('settingsOverlay');
const settingsModal       = $('settingsModal');
const btnCloseSettings    = $('btnCloseSettings');
const sttLangSelect       = $('sttLangSelect');
const responseLangSelect  = $('responseLangSelect');
const autoSendToggle      = $('autoSendToggle');
const ttsToggle           = $('ttsToggle');
const handsFreeToggle     = $('handsFreeToggle');
const memoryToggle        = $('memoryToggle');
const aboutInfo           = $('aboutInfo');

// Tools Modal
const toolsOverlay        = $('toolsOverlay');
const btnCloseTools       = $('btnCloseTools');

/* ─────────────────────────────── API Helpers ────────── */
const API = {
  base: '',

  async get(path) {
    const r = await fetch(this.base + path);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },

  async post(path, body) {
    const r = await fetch(this.base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || r.statusText);
    }
    return r.json();
  },

  async delete(path) {
    const r = await fetch(this.base + path, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
};

/* ─────────────────────────────── Toast System ───────── */
function toast(msg, type = 'info', duration = 3500) {
  const container = $('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    el.style.transition = 'all 0.3s ease';
    setTimeout(() => el.remove(), 320);
  }, duration);
}

/* ─────────────────────────────── Time Formatting ────── */
function formatTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/* ─────────────────────────────── Speech Sanitizer ───── */
function cleanTextForSpeech(text) {
  if (!text) return '';
  let s = text;
  s = s.replace(/```[a-zA-Z0-9_-]*\n[\s\S]*?```/g, ' Code block omitted for voice. ');
  s = s.replace(/```[\s\S]*?```/g, ' Code block omitted for voice. ');
  s = s.replace(/`([^`]+)`/g, '$1');
  s = s.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1');
  s = s.replace(/https?:\/\/\S+/g, '');
  s = s.replace(/^[ \t]*#+[ \t]+/gm, '');
  s = s.replace(/(\*\*|__)(.*?)\1/g, '$2');
  s = s.replace(/(\*|_)(.*?)\1/g, '$2');
  s = s.replace(/~~(.*?)~~/g, '$1');
  s = s.replace(/^[ \t]*>[ \t]*/gm, '');
  s = s.replace(/^[ \t]*[-*+]\s+/gm, '');
  s = s.replace(/^[ \t]*\d+\.\s+/gm, '');
  s = s.replace(/^[-*_]{3,}\s*$/gm, '');
  s = s.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '');
  return s.replace(/\s+/g, ' ').trim();
}

/* ─────────────────────────────── Chat Rendering ─────── */
function hideWelcome() {
  if (welcomeScreen) welcomeScreen.classList.add('hidden');
}

function appendMessage(role, content, id = null) {
  hideWelcome();
  const el = document.createElement('div');
  el.className = `message ${role}`;
  if (id) el.id = id;

  const avatar = role === 'user' ? '👤' : '◈';
  el.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body-wrapper">
      <div class="msg-bubble" data-bubble></div>
      <div class="msg-meta">
        <time class="msg-time">${formatTime()}</time>
        ${role === 'assistant' ? '<button class="msg-speak-btn" title="Speak this response">🔊</button>' : ''}
      </div>
    </div>`;

  messages.appendChild(el);
  setBubbleContent(el.querySelector('[data-bubble]'), content);

  if (role === 'assistant') {
    const speakBtn = el.querySelector('.msg-speak-btn');
    if (speakBtn) {
      speakBtn.addEventListener('click', () => {
        const bubble = el.querySelector('[data-bubble]');
        speakText(bubble.textContent || content);
      });
    }
  }

  scrollToBottom();
  return el;
}

function setBubbleContent(bubble, text) {
  let html = escapeHtml(text)
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code class="lang-${lang}">${code}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
  bubble.innerHTML = html;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function appendTypingIndicator() {
  hideWelcome();
  const el = document.createElement('div');
  el.className = 'message assistant';
  el.id = 'typingIndicator';
  el.innerHTML = `
    <div class="msg-avatar">◈</div>
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  messages.appendChild(el);
  scrollToBottom();
  return el;
}

function appendError(msg) {
  hideWelcome();
  const el = document.createElement('div');
  el.className = 'message assistant';
  el.innerHTML = `<div class="msg-avatar">◈</div><div class="msg-error">⚠ ${escapeHtml(msg)}</div>`;
  messages.appendChild(el);
  scrollToBottom();
}

function scrollToBottom() {
  chatArea.scrollTop = chatArea.scrollHeight;
}

/* ─────────────────────────────── Prompt Helper ──────── */
window.insertPrompt = function(promptText) {
  chatInput.value = promptText;
  autoResize(chatInput);
  sendMessage(promptText);
};

/* ─────────────────────────────── Send Message ───────── */
async function sendMessage(text, isVoiceInput = false) {
  if (!text || !text.trim() || state.isGenerating) return;

  // Dismiss any active speech review dock
  hideSpeechReviewDock();

  // If input was spoken through mic, automatically enable voice output
  if (isVoiceInput) {
    state.ttsEnabled = true;
    if (ttsToggle) ttsToggle.checked = true;
    btnTTS.classList.add('active');
    btnTTS.textContent = '🔊 Voice: ON';
    const statusTTS = $('statusTTS');
    if (statusTTS) statusTTS.textContent = 'Voice (Active)';
  }

  state.isGenerating = true;
  btnSend.disabled = true;

  appendMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';

  const typing = appendTypingIndicator();

  try {
    const resp = await fetch('/api/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: state.sessionId,
        include_memory: state.memoryEnabled,
        response_language: state.responseLanguage || 'en', // Strict requirement: English by default
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    typing.remove();
    const assistantEl = appendMessage('assistant', '');
    const bubble = assistantEl.querySelector('[data-bubble]');
    let fullText = '';

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        try {
          const data = JSON.parse(line.slice(5).trim());
          if (data.error) throw new Error(data.error);
          if (data.token) {
            fullText += data.token;
            setBubbleContent(bubble, fullText + '▊');
            scrollToBottom();
          }
          if (data.done) {
            setBubbleContent(bubble, fullText);
            state.currentModel = data.model || state.currentModel;
          }
        } catch (e) {
          if (e.message && !e.message.includes('JSON')) throw e;
        }
      }
    }

    // Automatically speak response if Voice mode is on OR message came from mic
    const shouldSpeak = isVoiceInput || state.ttsEnabled || state.handsFree;
    if (shouldSpeak && fullText) {
      speakText(fullText, () => {
        // Callback after speech finishes (hands-free continuation)
        if (state.handsFree && !state.isGenerating && !state.isRecording) {
          setTimeout(() => {
            if (state.handsFree) startRecording();
          }, 600);
        }
      });
    }

  } catch (err) {
    if (typing) typing.remove();
    appendError(err.message || 'Failed to get a response from NOVA.');
    console.error('Chat error:', err);
  } finally {
    state.isGenerating = false;
    btnSend.disabled = false;
  }
}

/* ─────────────────────────────── Clear Chat ─────────── */
async function clearChat() {
  try {
    await API.post('/api/chat/clear', { session_id: state.sessionId });
    stopSpeaking();
    stopRecording();
    hideSpeechReviewDock();
    messages.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    toast('Conversation memory cleared.', 'info');
  } catch (e) {
    toast('Failed to clear chat.', 'error');
  }
}

/* ─────────────────────────────── Language Mappings ──── */
const LANG_LABELS = {
  auto: 'Auto Detect',
  en:   'English',
  mr:   'Marathi / मराठी',
  hi:   'Hindi / हिन्दी',
};

function formatLangCode(code) {
  if (!code) return 'Auto';
  const c = code.toLowerCase().trim();
  if (c === 'en') return 'English';
  if (c === 'mr') return 'Marathi';
  if (c === 'hi') return 'Hindi';
  return c.toUpperCase();
}

/* ─────────────────────────────── Speech Input (STT) ─── */
function updateVoiceUI(statusText, isRecording = false) {
  if (isRecording) {
    btnMic.classList.add('recording');
    $('statusMic').textContent = '🔴 Listening…';
    voiceStatusPill.classList.remove('hidden');
    voiceStatusText.textContent = statusText || 'Listening… Speak in English, Marathi, or Hindi';
  } else {
    btnMic.classList.remove('recording');
    $('statusMic').textContent = 'Ready';
    voiceStatusPill.classList.add('hidden');
  }
}

async function startRecording() {
  if (state.isRecording) {
    stopRecording();
    return;
  }

  stopSpeaking();
  hideSpeechReviewDock();

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    toast('Microphone not supported by this browser.', 'error');
    $('statusMic').textContent = 'Unsupported';
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.mediaStream = stream;
    state.audioChunks = [];

    let mimeType = '';
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus';
    } else if (MediaRecorder.isTypeSupported('audio/webm')) {
      mimeType = 'audio/webm';
    } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
      mimeType = 'audio/ogg;codecs=opus';
    }

    const options = mimeType ? { mimeType } : {};
    const recorder = new MediaRecorder(stream, options);
    state.mediaRecorder = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        state.audioChunks.push(e.data);
      }
    };

    recorder.onstop = async () => {
      if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(t => t.stop());
        state.mediaStream = null;
      }

      voiceStatusText.textContent = '⏳ Analyzing acoustic waveform…';
      $('statusMic').textContent = 'Transcribing…';

      try {
        if (!state.audioChunks.length) {
          updateVoiceUI('', false);
          return;
        }

        const blobType = mimeType || 'audio/webm';
        const blob = new Blob(state.audioChunks, { type: blobType });

        if (blob.size < 1000) {
          toast('No audio recorded. Please try speaking into the mic.', 'info');
          updateVoiceUI('', false);
          state.isRecording = false;
          return;
        }

        const form = new FormData();
        form.append('file', blob, 'speech_recording.webm');

        // Requirement 4: Use language=None for Auto Detect.
        // Only pass language if user explicitly chose English, Marathi, or Hindi.
        if (state.sttLanguage && state.sttLanguage !== 'auto') {
          form.append('language', state.sttLanguage);
        }

        const resp = await fetch('/api/voice/transcribe', { method: 'POST', body: form });
        const data = await resp.json();

        if (data.transcription && data.transcription.trim()) {
          const rawText = data.transcription.trim();
          const detectedCode = data.detected_language || (state.sttLanguage !== 'auto' ? state.sttLanguage : 'unknown');
          const detectedName = formatLangCode(detectedCode);
          const conf = data.confidence !== undefined ? Math.round(data.confidence * 100) : null;

          // Requirement 8: Do not silently translate! Display exact recognized text.
          chatInput.value = rawText;
          autoResize(chatInput);

          // Requirement 9: Show review dock to let user edit transcription before sending
          showSpeechReviewDock(rawText, detectedName, conf);

        } else {
          toast('No clear speech detected. Please speak closer to the mic.', 'info');
        }
      } catch (e) {
        toast(`Transcription error: ${e.message}`, 'error');
      } finally {
        updateVoiceUI('', false);
        state.isRecording = false;
      }
    };

    recorder.start();
    state.isRecording = true;
    const langDesc = state.sttLanguage === 'auto' ? 'Auto Detect (English / Marathi / Hindi)' : formatLangCode(state.sttLanguage);
    updateVoiceUI(`Listening… [${langDesc}]`, true);

  } catch (err) {
    console.error('Microphone access error:', err);
    updateVoiceUI('', false);
    state.isRecording = false;
    $('statusMic').textContent = 'Error';
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      toast('Microphone permission was denied. Please allow mic access in your browser address bar.', 'error', 5000);
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      toast('No microphone hardware detected on your computer.', 'error');
    } else {
      toast(`Microphone error: ${err.message}`, 'error');
    }
  }
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }
  state.isRecording = false;
  updateVoiceUI('', false);
}

function cancelRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.audioChunks = [];
    state.mediaRecorder.stop();
  }
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach(t => t.stop());
    state.mediaStream = null;
  }
  state.isRecording = false;
  updateVoiceUI('', false);
  toast('Recording cancelled.', 'info');
}

/* ─────────────────────────────── Speech Review Dock ─── */
function showSpeechReviewDock(text, langName, conf) {
  if (!speechReviewDock) return;
  speechDetectedTag.textContent = `🎙 Language: ${langName}`;
  speechConfidenceTag.textContent = conf !== null ? `Confidence: ${conf}%` : '';
  speechReviewText.textContent = text;
  speechReviewDock.classList.remove('hidden');

  // If user enabled auto-send AND confidence is high (>75%), offer a brief 2-second grace period
  if (state.autoSendVoice && (conf === null || conf >= 75)) {
    let secondsLeft = 2;
    btnConfirmSendVoice.textContent = `Send (${secondsLeft}s) ↵`;
    clearTimeout(state.speechReviewTimer);
    state.speechReviewTimer = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft > 0) {
        btnConfirmSendVoice.textContent = `Send (${secondsLeft}s) ↵`;
      } else {
        clearInterval(state.speechReviewTimer);
        btnConfirmSendVoice.textContent = `Send Now ↵`;
        sendMessage(chatInput.value || text, true);
      }
    }, 1000);
  } else {
    // Focus chat input for easy user review & editing
    btnConfirmSendVoice.textContent = `Send Now ↵`;
    chatInput.focus();
    chatInput.select();
  }
}

function hideSpeechReviewDock() {
  if (state.speechReviewTimer) {
    clearInterval(state.speechReviewTimer);
    state.speechReviewTimer = null;
  }
  if (speechReviewDock) speechReviewDock.classList.add('hidden');
}

/* ─────────────────────────────── Voice Output (TTS) ─── */
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
  window.speechSynthesis.getVoices();
}

function setSpeakingState(isSpeaking) {
  state.isSpeaking = isSpeaking;
  if (isSpeaking) {
    btnStopTTS.classList.remove('hidden');
    btnTTS.classList.add('active');
  } else {
    btnStopTTS.classList.add('hidden');
    if (!state.ttsEnabled && !state.handsFree) {
      btnTTS.classList.remove('active');
    }
  }
}

async function speakText(rawText, onComplete = null) {
  const clean = cleanTextForSpeech(rawText);
  if (!clean) {
    if (onComplete) onComplete();
    return;
  }

  stopSpeaking();
  setSpeakingState(true);

  if ('speechSynthesis' in window) {
    try {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }
    } catch (e) {}

    const utt = new SpeechSynthesisUtterance(clean);
    utt.rate = 1.0;

    const hasDevanagari = /[\u0900-\u097F]/.test(clean);
    const voices = window.speechSynthesis.getVoices();

    if (hasDevanagari) {
      const mrVoice = voices.find(v => v.lang === 'mr-IN' || v.lang.startsWith('mr') || (v.name && v.name.toLowerCase().includes('marathi')));
      const hiVoice = voices.find(v => v.lang === 'hi-IN' || v.lang.startsWith('hi') || (v.name && v.name.toLowerCase().includes('hindi')));
      const devVoice = mrVoice || hiVoice;
      if (devVoice) {
        utt.voice = devVoice;
        utt.lang = devVoice.lang;
      } else {
        utt.lang = 'mr-IN';
      }
    } else {
      const enVoice = voices.find(v => v.lang === 'en-US' || v.lang === 'en-IN' || v.lang.startsWith('en'));
      if (enVoice) {
        utt.voice = enVoice;
        utt.lang = enVoice.lang;
      } else {
        utt.lang = 'en-US';
      }
    }

    utt.onend = () => {
      setSpeakingState(false);
      if (onComplete) onComplete();
    };

    utt.onerror = async (e) => {
      console.warn('Browser TTS error, fallback to local backend TTS:', e);
      try {
        await API.post('/api/voice/tts/speak', { text: clean });
      } catch (err) {
        console.warn('Server TTS failed:', err);
      } finally {
        setSpeakingState(false);
        if (onComplete) onComplete();
      }
    };

    window.speechSynthesis.speak(utt);
  } else {
    try {
      await API.post('/api/voice/tts/speak', { text: clean });
    } catch (e) {
      console.warn('Server TTS failed:', e);
    } finally {
      setSpeakingState(false);
      if (onComplete) onComplete();
    }
  }
}

function stopSpeaking() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  API.post('/api/voice/tts/stop', {}).catch(() => {});
  setSpeakingState(false);
}

/* ─────────────────────────────── Language Selection ─── */
function setResponseLanguage(lang) {
  state.responseLanguage = lang;
  if (responseLangSelect) responseLangSelect.value = lang;
  if (btnLangToggle) {
    if (lang === 'mr') {
      btnLangToggle.textContent = '🌐 Reply: Marathi';
      btnLangToggle.classList.add('active');
    } else if (lang === 'hi') {
      btnLangToggle.textContent = '🌐 Reply: Hindi';
      btnLangToggle.classList.add('active');
    } else if (lang === 'auto') {
      btnLangToggle.textContent = '🌐 Reply: Match User';
      btnLangToggle.classList.add('active');
    } else {
      btnLangToggle.textContent = '🌐 Reply: English';
      btnLangToggle.classList.remove('active');
    }
  }
}

function setSTTLanguage(lang) {
  state.sttLanguage = lang;
  if (sttLangSelect) sttLangSelect.value = lang;
  if (btnSTTIndicator) {
    const label = lang === 'auto' ? 'Auto Detect' : formatLangCode(lang);
    btnSTTIndicator.textContent = `🎙 STT: ${label}`;
    btnSTTIndicator.classList.toggle('active', lang !== 'auto');
  }
}

/* ─────────────────────────────── Vision ─────────────── */
async function captureImage() {
  $('statusCam').textContent = '📷 Capturing…';
  try {
    const data = await API.post('/api/vision/capture', {});
    state.visionCapture = data.image_base64;
    visionImg.src = `data:image/jpeg;base64,${data.image_base64}`;
    visionAnswer.textContent = 'Frame captured. Ask a question below!';
    visionPreview.classList.remove('hidden');
    $('statusCam').textContent = 'Captured';
    toast('Vision frame captured.', 'success');
  } catch (e) {
    toast(`Camera error: ${e.message}`, 'error');
    $('statusCam').textContent = 'Error';
  }
}

async function analyseImage() {
  if (!state.visionCapture) { toast('No image captured.', 'error'); return; }
  const question = visionQuestion.value || 'What do you see?';
  visionAnswer.textContent = '🔍 Shadow Sight analyzing…';
  btnAnalyse.disabled = true;

  try {
    const data = await API.post('/api/vision/analyse', { question });
    visionAnswer.textContent = data.answer;
    const context = `[Webcam analysis by ${data.model}]\n${data.answer}`;
    appendMessage('assistant', context);
  } catch (e) {
    visionAnswer.textContent = `Error: ${e.message}`;
    toast('Vision analysis failed.', 'error');
  } finally {
    btnAnalyse.disabled = false;
  }
}

/* ─────────────────────────────── Memory Vault ───────── */
async function loadMemories() {
  try {
    const data = await API.get('/api/memory/');
    renderMemories(data.memories || []);
  } catch (e) {
    console.warn('Failed to load memories:', e);
  }
}

function renderMemories(mems) {
  if (!memoryList) return;
  if (!mems.length) {
    memoryList.innerHTML = '<div class="memory-empty">Memory vault empty.</div>';
    return;
  }
  memoryList.innerHTML = mems.map(m => `
    <div class="memory-item" data-id="${m.id}">
      <span title="${escapeHtml(m.content)}">${escapeHtml(m.content)}</span>
      <button class="memory-del-btn" onclick="deleteMemory(${m.id})">✕</button>
    </div>`).join('');
}

async function saveMemory() {
  const content = memoryInput.value.trim();
  if (!content) return;
  try {
    const res = await API.post('/api/memory/save', { content, tags: 'user' });
    memoryInput.value = '';
    toast('Recorded into Shadow Memory.', 'success');
    loadMemories();
  } catch (e) {
    toast(`Failed to save memory: ${e.message}`, 'error');
  }
}

window.deleteMemory = async function(id) {
  try {
    await API.delete(`/api/memory/${id}`);
    toast('Memory purged.', 'info');
    loadMemories();
  } catch (e) {
    toast('Failed to delete memory.', 'error');
  }
};

async function clearAllMemories() {
  if (!confirm('Purge all long-term memories?')) return;
  try {
    await API.delete('/api/memory/');
    toast('All memories purged.', 'info');
    loadMemories();
  } catch (e) {
    toast('Failed to clear memories.', 'error');
  }
}

/* ─────────────────────────────── System Tools ───────── */
window.launchApp = async function(appName) {
  try {
    const res = await API.post('/api/tools/open-app', { app_name: appName });
    toast(`Launched: ${appName}`, 'success');
  } catch (e) {
    toast(`Could not launch ${appName}: ${e.message}`, 'error');
  }
};

/* ─────────────────────────────── Status & Polling ───── */
async function pollStatus() {
  try {
    const s = await API.get('/api/status/');

    // Ollama
    const dotOllama = $('statusOllama')?.querySelector('.status-dot');
    if (dotOllama) {
      dotOllama.className = 'status-dot ' + (s.llm.running ? 'dot-online' : 'dot-checking');
    }
    $('statusOllamaText').textContent = s.llm.running ? 'Awakened (Online)' : 'Offline';

    // Model name
    const modelName = s.llm.selected_model || state.currentModel || 'none';
    $('statusModelText').textContent = modelName;

    // Model list
    if (s.llm.available_models && s.llm.available_models.length) {
      modelList.innerHTML = s.llm.available_models.map(m => `
        <div class="model-item ${m === s.llm.selected_model ? 'active' : ''}" onclick="switchModel('${escapeHtml(m)}')">
          <span>${escapeHtml(m)}</span>
          ${m === s.llm.selected_model ? '<span class="status-dot dot-online"></span>' : ''}
        </div>`).join('');

      const opts = s.llm.available_models.map(m =>
        `<option value="${escapeHtml(m)}" ${m === s.llm.selected_model ? 'selected' : ''}>${escapeHtml(m)}</option>`
      ).join('');
      modelSelect.innerHTML = opts;
    } else {
      modelList.innerHTML = `<div class="model-list-empty">No local models. Run: ollama pull llama3.2:3b</div>`;
    }

    // System resources
    const sys = await API.get('/api/status/system');
    if (!sys.error) {
      $('cpuFill').style.width = `${sys.cpu_percent}%`;
      $('cpuPct').textContent  = `${sys.cpu_percent}%`;
      $('ramFill').style.width = `${sys.ram_percent}%`;
      $('ramPct').textContent  = `${sys.ram_used_gb}/${sys.ram_total_gb}G`;
    }

    // Diagnostics panel
    aboutInfo.textContent =
      `NOVA S-Class v${s.app.version}\n` +
      `System Core: ${s.llm.selected_model || 'none'} (Ollama local)\n` +
      `Session ID: ${state.sessionId}\n` +
      `Shadow Memory: ${s.memory.count} records\n` +
      `STT Engine: ${s.voice.stt_available ? '✓ faster-whisper (neural acoustic auto-detect)' : '✗ missing'}\n` +
      `TTS Engine: ${s.voice.tts_available ? '✓ pyttsx3 / Web Speech' : '✗ missing'}\n` +
      `Sight Camera: ${s.vision.camera_available ? '✓ ready' : '✗ offline'}\n` +
      `Isolation: ${s.app.offline_mode ? '🔒 100% Local (Airgapped)' : 'Online'}`;

  } catch (e) {
    console.warn('Status poll failed:', e);
  }
}

async function switchModel(modelName) {
  try {
    await API.post('/api/chat/model', { model: modelName });
    state.currentModel = modelName;
    toast(`Active Core Model: ${modelName}`, 'success');
    pollStatus();
  } catch (e) {
    toast(`Model switch failed: ${e.message}`, 'error');
  }
}

/* ─────────────────────────────── Auto-resize Textarea ─ */
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

/* ─────────────────────────────── Event Listeners ────── */

// Chat input
chatInput.addEventListener('input', () => autoResize(chatInput));
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(chatInput.value);
  }
});
btnSend.addEventListener('click', () => sendMessage(chatInput.value));
btnClear.addEventListener('click', clearChat);

// Mic button: push to toggle recording
btnMic.addEventListener('click', () => {
  if (state.isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

if (btnCancelVoice) {
  btnCancelVoice.addEventListener('click', cancelRecording);
}

// Speech Review Dock Actions (Requirement 9)
if (btnConfirmSendVoice) {
  btnConfirmSendVoice.addEventListener('click', () => {
    sendMessage(chatInput.value || speechReviewText.textContent, true);
  });
}
if (btnEditVoiceInput) {
  btnEditVoiceInput.addEventListener('click', () => {
    hideSpeechReviewDock();
    chatInput.focus();
  });
}
if (btnCancelVoiceReview) {
  btnCancelVoiceReview.addEventListener('click', () => {
    hideSpeechReviewDock();
    chatInput.value = '';
    autoResize(chatInput);
  });
}

// Stop speaking
btnStopTTS.addEventListener('click', stopSpeaking);

// Hands-free toggle
btnHandsFree.addEventListener('click', () => {
  state.handsFree = !state.handsFree;
  handsFreeToggle.checked = state.handsFree;
  btnHandsFree.classList.toggle('active', state.handsFree);
  btnHandsFree.textContent = state.handsFree ? '🎙 Hands-Free: ON' : '🎙 Hands-Free: Off';
  toast(state.handsFree ? 'Hands-Free activated. NOVA listens after speaking.' : 'Hands-Free off.', 'info');
  if (state.handsFree && !state.isRecording && !state.isGenerating && !state.isSpeaking) {
    startRecording();
  }
});

handsFreeToggle.addEventListener('change', () => {
  state.handsFree = handsFreeToggle.checked;
  btnHandsFree.classList.toggle('active', state.handsFree);
  btnHandsFree.textContent = state.handsFree ? '🎙 Hands-Free: ON' : '🎙 Hands-Free: Off';
});

// TTS toggle
btnTTS.addEventListener('click', () => {
  state.ttsEnabled = !state.ttsEnabled;
  ttsToggle.checked = state.ttsEnabled;
  btnTTS.classList.toggle('active', state.ttsEnabled);
  btnTTS.textContent = state.ttsEnabled ? '🔊 Voice: ON' : '🔊 Voice: Off';
  toast(state.ttsEnabled ? 'Voice output enabled.' : 'Voice output disabled.', 'info');
  if (!state.ttsEnabled) stopSpeaking();
});

ttsToggle.addEventListener('change', () => {
  state.ttsEnabled = ttsToggle.checked;
  btnTTS.classList.toggle('active', state.ttsEnabled);
  btnTTS.textContent = state.ttsEnabled ? '🔊 Voice: ON' : '🔊 Voice: Off';
  if (!state.ttsEnabled) stopSpeaking();
});

// Memory toggle
memoryToggle.addEventListener('change', () => {
  state.memoryEnabled = memoryToggle.checked;
  toast(state.memoryEnabled ? 'Shadow memory context enabled.' : 'Shadow memory disabled.', 'info');
});

// Auto-send voice toggle
if (autoSendToggle) {
  autoSendToggle.addEventListener('change', () => {
    state.autoSendVoice = autoSendToggle.checked;
    toast(state.autoSendVoice ? 'Auto-send voice enabled.' : 'Review before sending enabled.', 'info');
  });
}

// Response Language toggle & select (Requirement 7)
if (btnLangToggle) {
  btnLangToggle.addEventListener('click', () => {
    const cycle = { en: 'mr', mr: 'hi', hi: 'auto', auto: 'en' };
    const next = cycle[state.responseLanguage] || 'en';
    setResponseLanguage(next);
    toast(`NOVA Response Language: ${LANG_LABELS[next] || next}`, 'info');
  });
}

if (responseLangSelect) {
  responseLangSelect.addEventListener('change', () => {
    setResponseLanguage(responseLangSelect.value);
    toast(`Response Language: ${responseLangSelect.options[responseLangSelect.selectedIndex].text}`, 'info');
  });
}

// Speech Recognition Language selector & indicator (Requirement 5 & 6)
if (btnSTTIndicator) {
  btnSTTIndicator.addEventListener('click', () => {
    const cycle = { auto: 'en', en: 'mr', mr: 'hi', hi: 'auto' };
    const next = cycle[state.sttLanguage] || 'auto';
    setSTTLanguage(next);
    toast(`Speech Recognition Language: ${LANG_LABELS[next] || next}`, 'info');
  });
}

if (sttLangSelect) {
  sttLangSelect.addEventListener('change', () => {
    setSTTLanguage(sttLangSelect.value);
    toast(`Speech Recognition: ${sttLangSelect.options[sttLangSelect.selectedIndex].text}`, 'info');
  });
}

// Sidebar Navigation Tabs (Requirement B)
if (navChat) {
  navChat.addEventListener('click', () => {
    setActiveNav(navChat);
    chatInput.focus();
  });
}
if (navMemory) {
  navMemory.addEventListener('click', () => {
    setActiveNav(navMemory);
    memorySection?.scrollIntoView({ behavior: 'smooth' });
    memoryInput?.focus();
  });
}
if (navVoice) {
  navVoice.addEventListener('click', () => {
    setActiveNav(navVoice);
    if (!state.isRecording) startRecording();
  });
}
if (navVision) {
  navVision.addEventListener('click', () => {
    setActiveNav(navVision);
    captureImage();
  });
}
if (navTools) {
  navTools.addEventListener('click', () => {
    setActiveNav(navTools);
    toolsOverlay?.classList.remove('hidden');
  });
}
if (navSettings) {
  navSettings.addEventListener('click', () => {
    setActiveNav(navSettings);
    settingsOverlay?.classList.remove('hidden');
  });
}

function setActiveNav(activeBtn) {
  [navChat, navMemory, navVoice, navVision, navTools, navSettings].forEach(btn => {
    if (btn) btn.classList.remove('active');
  });
  if (activeBtn) activeBtn.classList.add('active');
}

// Camera
btnCamera.addEventListener('click', captureImage);
btnCloseVision.addEventListener('click', () => {
  visionPreview.classList.add('hidden');
  state.visionCapture = null;
  $('statusCam').textContent = 'Ready';
});
btnAnalyse.addEventListener('click', analyseImage);
visionQuestion.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') analyseImage();
});

// Sidebar Toggle
sidebarToggle.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

// Settings Modal
btnSettings.addEventListener('click', () => settingsOverlay.classList.remove('hidden'));
btnCloseSettings.addEventListener('click', () => settingsOverlay.classList.add('hidden'));
settingsOverlay.addEventListener('click', (e) => {
  if (e.target === settingsOverlay) settingsOverlay.classList.add('hidden');
});
btnApplyModel.addEventListener('click', () => {
  const m = modelSelect.value;
  if (m) { switchModel(m); settingsOverlay.classList.add('hidden'); }
});

// Tools Modal
if (btnCloseTools) {
  btnCloseTools.addEventListener('click', () => toolsOverlay.classList.add('hidden'));
}
if (toolsOverlay) {
  toolsOverlay.addEventListener('click', (e) => {
    if (e.target === toolsOverlay) toolsOverlay.classList.add('hidden');
  });
}

// Memory CRUD
btnSaveMemory.addEventListener('click', saveMemory);
memoryInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') saveMemory(); });
btnClearMemory.addEventListener('click', clearAllMemories);

/* ─────────────────────────────── Initialise ──────────── */
(async function init() {
  setResponseLanguage('en');  // Guarantee Response Language default: English
  setSTTLanguage('auto');     // Guarantee Speech Recognition default: Auto Detect
  await pollStatus();
  await loadMemories();
  setInterval(pollStatus, 15_000);
  console.log('%c[SYSTEM AWAKENED] NOVA Shadow Monarch AI System online.', 'color:#00f0ff;font-weight:bold;font-size:15px;');
})();
