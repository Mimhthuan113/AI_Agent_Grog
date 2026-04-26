import { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { getApiUrl, isCapacitorNative } from '../../api/config';
import './OrbAvatar.css';

const STATES = {
  IDLE: 'idle',
  LISTENING: 'listening',
  THINKING: 'thinking',
  SPEAKING: 'speaking',
};

function VoiceOrbInner({ onResult, onSpeakEnd, onStateChange, isThinking, speakText }, ref) {
  const [state, setState] = useState(STATES.IDLE);
  const [transcript, setTranscript] = useState('');
  const [volume, setVolume] = useState(0);
  const recognitionRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);
  const streamRef = useRef(null);

  // Notify parent khi state đổi (để pause wake-word lúc listening/speaking)
  useEffect(() => {
    if (typeof onStateChange === 'function') onStateChange(state);
  }, [state, onStateChange]);

  // ── Audio Visualizer ──────────────────────────
  // Define trước startListening để onstart/onend closure không truy cập TDZ
  const startAudioVisualizer = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateVolume = () => {
        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        setVolume(avg / 128);
        animFrameRef.current = requestAnimationFrame(updateVolume);
      };
      updateVolume();
    } catch (err) {
      console.error('Microphone access error:', err);
    }
  }, []);

  const stopAudioVisualizer = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setVolume(0);
  }, []);

  // ── Native Speech (Capacitor plugin) ──────────────
  // Dùng cho APK Android — Web Speech API không có trong WebView nguyên bản
  const nativeListenerRef = useRef(null);
  const nativeFinalTextRef = useRef('');

  const startNativeListening = useCallback(async () => {
    let SpeechRecognition;
    try {
      ({ SpeechRecognition } = await import('@capacitor-community/speech-recognition'));
    } catch (err) {
      console.error('Plugin speech-recognition không cài:', err);
      alert('Plugin speech-recognition không sẵn sàng.');
      return;
    }

    // Permission check
    try {
      const perm = await SpeechRecognition.checkPermissions();
      if (perm.permission !== 'granted') {
        const req = await SpeechRecognition.requestPermissions();
        if (req.permission !== 'granted') {
          alert('Cần cấp quyền micro để nói với Aisha.');
          return;
        }
      }
    } catch (err) {
      console.error('Permission error:', err);
      return;
    }

    setState(STATES.LISTENING);
    setTranscript('');
    nativeFinalTextRef.current = '';
    startAudioVisualizer();

    // Đăng ký listener trước khi start
    try {
      nativeListenerRef.current = await SpeechRecognition.addListener(
        'partialResults',
        (data) => {
          const text = data?.matches?.[0] || '';
          if (text) {
            nativeFinalTextRef.current = text;
            setTranscript(text);
          }
        },
      );
    } catch (err) {
      console.error('Listener error:', err);
    }

    try {
      // start() block đến khi user dừng nói (~5s im lặng) hoặc được stop()
      await SpeechRecognition.start({
        language: 'vi-VN',
        maxResults: 1,
        prompt: '',
        partialResults: true,
        popup: false,
      });
    } catch (err) {
      console.error('Native speech start error:', err);
    } finally {
      // Cleanup
      if (nativeListenerRef.current) {
        try { await nativeListenerRef.current.remove(); } catch { /* ignore */ }
        nativeListenerRef.current = null;
      }
      stopAudioVisualizer();

      const finalText = nativeFinalTextRef.current.trim();
      if (finalText) {
        setState(STATES.THINKING);
        onResult(finalText);
      } else {
        setState(STATES.IDLE);
      }
    }
  }, [onResult, startAudioVisualizer, stopAudioVisualizer]);

  const stopNativeListening = useCallback(async () => {
    try {
      const { SpeechRecognition } = await import('@capacitor-community/speech-recognition');
      await SpeechRecognition.stop();
    } catch { /* ignore */ }
  }, []);

  // ── Web Speech (Chrome/Edge) ──────────────────────
  const startWebListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      alert('Trình duyệt không hỗ trợ nhận diện giọng nói. Hãy dùng Chrome hoặc Edge.');
      return;
    }

    const recognition = new SR();
    recognition.lang = 'vi-VN';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setState(STATES.LISTENING);
      setTranscript('');
      startAudioVisualizer();
    };

    recognition.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      setTranscript(final || interim);
    };

    recognition.onend = () => {
      stopAudioVisualizer();
      if (transcript || recognitionRef.current?._lastTranscript) {
        const finalText = transcript || recognitionRef.current?._lastTranscript || '';
        if (finalText.trim()) {
          setState(STATES.THINKING);
          onResult(finalText.trim());
        } else {
          setState(STATES.IDLE);
        }
      } else {
        setState(STATES.IDLE);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      stopAudioVisualizer();
      setState(STATES.IDLE);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [onResult, transcript, startAudioVisualizer, stopAudioVisualizer]);

  // ── Dispatcher (chọn backend phù hợp) ─────────────
  const startListening = useCallback(() => {
    if (isCapacitorNative()) {
      startNativeListening();
    } else {
      startWebListening();
    }
  }, [startNativeListening, startWebListening]);

  const stopListening = useCallback(() => {
    if (isCapacitorNative()) {
      stopNativeListening();
      return;
    }
    if (recognitionRef.current) {
      recognitionRef.current._lastTranscript = transcript;
      recognitionRef.current.stop();
    }
  }, [transcript, stopNativeListening]);

  // ── Text-to-Speech (Edge TTS — giọng HoaiMy nữ) ────
  const audioRef = useRef(null);

  useEffect(() => {
    if (!speakText || state === STATES.SPEAKING) return;

    setState(STATES.SPEAKING);

    const playTTS = async () => {
      try {
        const API = getApiUrl();
        const token = localStorage.getItem('token');
        const resp = await fetch(`${API}/voice/tts`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ text: speakText }),
        });

        if (!resp.ok) throw new Error(`TTS failed: ${resp.status}`);

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);

        if (audioRef.current) {
          audioRef.current.pause();
        }

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setState(STATES.IDLE);
          URL.revokeObjectURL(url);
          if (onSpeakEnd) onSpeakEnd();
        };

        audio.onerror = () => {
          setState(STATES.IDLE);
          URL.revokeObjectURL(url);
          if (onSpeakEnd) onSpeakEnd();
        };

        await audio.play();
      } catch (err) {
        console.error('[Aisha TTS] Error:', err);
        setState(STATES.IDLE);
        if (onSpeakEnd) onSpeakEnd();
      }
    };

    playTTS();
  }, [speakText]);

  // ── isThinking from parent ────────────────────
  useEffect(() => {
    if (isThinking) setState(STATES.THINKING);
  }, [isThinking]);

  // ── Click handler ─────────────────────────────
  const handleClick = () => {
    if (state === STATES.IDLE) {
      startListening();
    } else if (state === STATES.LISTENING) {
      stopListening();
    } else if (state === STATES.SPEAKING) {
      speechSynthesis.cancel();
      setState(STATES.IDLE);
    }
  };

  // Expose imperative API cho parent (wake-word trigger)
  useImperativeHandle(ref, () => ({
    startListening: () => {
      if (state === STATES.IDLE) startListening();
    },
    stopListening,
    getState: () => state,
  }), [state, startListening, stopListening]);

  // ── Labels ────────────────────────────────────
  const stateLabels = {
    [STATES.IDLE]: 'Nhấn để nói',
    [STATES.LISTENING]: 'Đang nghe...',
    [STATES.THINKING]: 'Đang xử lý...',
    [STATES.SPEAKING]: 'Đang trả lời...',
  };

  const orbScale = state === STATES.LISTENING ? 1 + volume * 0.3 : 1;

  return (
    <div className="voice-orb-container">
      <div
        className={`voice-orb voice-orb--${state}`}
        onClick={handleClick}
        style={{ transform: `scale(${orbScale})` }}
      >
        <div className="voice-orb__inner">
          {state === STATES.LISTENING && (
            <div className="voice-orb__waves">
              <span></span><span></span><span></span><span></span><span></span>
            </div>
          )}
          {state === STATES.THINKING && (
            <div className="voice-orb__dots">
              <span></span><span></span><span></span>
            </div>
          )}
          {state === STATES.SPEAKING && (
            <div className="voice-orb__pulse"></div>
          )}
          {state === STATES.IDLE && (
            <svg className="voice-orb__mic" viewBox="0 0 24 24" fill="currentColor" width="32" height="32">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5z"/>
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
          )}
        </div>
      </div>

      <p className="voice-orb__label">{stateLabels[state]}</p>

      {transcript && state === STATES.LISTENING && (
        <p className="voice-orb__transcript">{transcript}</p>
      )}
    </div>
  );
}

const VoiceOrb = forwardRef(VoiceOrbInner);
export default VoiceOrb;
