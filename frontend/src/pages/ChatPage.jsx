import { useState, useRef, useEffect, useCallback } from 'react';
import api from '../api/client';
import useStore from '../store/useStore';
import VoiceOrb from '../components/VoiceOrb';
import './ChatPage.css';

const SUGGESTIONS = [
  { icon: '💡', text: 'Bật đèn phòng ngủ' },
  { icon: '🌡', text: 'Nhiệt độ phòng' },
  { icon: '🔒', text: 'Khóa cửa' },
  { icon: '🕐', text: 'Mấy giờ rồi' },
  { icon: '👋', text: 'Xin chào' },
  { icon: '❓', text: 'Bạn là ai' },
];

export default function ChatPage() {
  const { messages, addMessage } = useStore();
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [speakText, setSpeakText] = useState('');
  const [lastResponse, setLastResponse] = useState(null);
  const [mode, setMode] = useState('voice');
  const historyEndRef = useRef(null);

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    addMessage({ role: 'user', text: text.trim() });
    setInput('');
    setIsThinking(true);
    setLastResponse(null);

    try {
      const { data } = await api.post('/chat', { message: text.trim() });
      const aiMsg = {
        role: 'ai',
        text: data.response,
        success: data.success,
        category: data.category || 'general',
        command: data.command,
      };
      addMessage(aiMsg);
      setLastResponse(aiMsg);
      setSpeakText(data.response);
    } catch (err) {
      const errMsg = {
        role: 'ai',
        text: 'Có lỗi kết nối. Vui lòng thử lại.',
        success: false,
      };
      addMessage(errMsg);
      setLastResponse(errMsg);
    } finally {
      setIsThinking(false);
    }
  }, [addMessage]);

  const handleVoiceResult = useCallback((text) => {
    sendMessage(text);
  }, [sendMessage]);

  const handleSpeakEnd = useCallback(() => {
    setSpeakText('');
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const getCategoryLabel = (cat) => {
    const labels = {
      smart_home: '🏠 Nhà thông minh',
      time_query: '🕐 Thời gian',
      greeting: '👋 Chào hỏi',
      self_intro: '🤖 Giới thiệu',
      general_chat: '💬 Hội thoại',
      dangerous: '🛡️ Bảo mật',
      thanks: '💖 Cảm ơn',
      goodbye: '👋 Tạm biệt',
      compliment: '🥰 Khen ngợi',
    };
    return labels[cat] || '💬 Trả lời';
  };

  // Only show history messages (skip welcome + last shown response)
  const historyMessages = messages.filter(m => m.id !== 'welcome').slice(0, -2);

  return (
    <div className="chat-page">

      {/* ── Mode Toggle ───────────────────────── */}
      <div className="mode-toggle">
        <button className={`mode-btn ${mode === 'voice' ? 'active' : ''}`}
          onClick={() => setMode('voice')}>🎙 Giọng nói</button>
        <button className={`mode-btn ${mode === 'text' ? 'active' : ''}`}
          onClick={() => setMode('text')}>⌨ Văn bản</button>
      </div>

      {/* ── Siri Center ───────────────────────── */}
      <div className="siri-center">

        {/* Voice Orb */}
        {mode === 'voice' && (
          <VoiceOrb
            onResult={handleVoiceResult}
            onSpeakEnd={handleSpeakEnd}
            isThinking={isThinking}
            speakText={speakText}
          />
        )}

        {/* AI Response Card */}
        {isThinking && (
          <div className="siri-response">
            <div className="thinking-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}

        {lastResponse && !isThinking && (
          <div className="siri-response" key={lastResponse.text}>
            <p className="siri-response__text">{lastResponse.text}</p>
            <div className="siri-response__category">
              {getCategoryLabel(lastResponse.category)}
              {lastResponse.success !== undefined && (
                <span className={`siri-response__status ${lastResponse.success ? 'ok' : 'fail'}`}>
                  {lastResponse.success ? '✓' : '✗'}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Suggestions */}
        {!isThinking && !lastResponse && (
          <div className="siri-suggestions">
            {SUGGESTIONS.map((s, i) => (
              <button key={i} className="siri-chip"
                onClick={() => sendMessage(s.text)} disabled={isThinking}>
                {s.icon} {s.text}
              </button>
            ))}
          </div>
        )}

        {/* Show suggestions again after response */}
        {lastResponse && !isThinking && (
          <div className="siri-suggestions" style={{ marginTop: 8 }}>
            {SUGGESTIONS.slice(0, 4).map((s, i) => (
              <button key={i} className="siri-chip"
                onClick={() => { setLastResponse(null); sendMessage(s.text); }}
                disabled={isThinking}>
                {s.icon} {s.text}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Chat History (minimal) ─────────────── */}
      {historyMessages.length > 0 && (
        <div className="chat-history">
          {historyMessages.map((msg, i) => (
            <div key={i} className={`chat-history-item chat-history-item--${msg.role}`}>
              <div className="chat-history-item__bubble">
                {msg.text?.length > 60 ? msg.text.slice(0, 60) + '...' : msg.text}
              </div>
            </div>
          ))}
          <div ref={historyEndRef} />
        </div>
      )}

      {/* ── Text Input ────────────────────────── */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Hỏi Aisha bất cứ điều gì..."
          disabled={isThinking}
        />
        <button type="submit" disabled={!input.trim() || isThinking}>➤</button>
      </form>
    </div>
  );
}
