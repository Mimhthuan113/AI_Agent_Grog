import { useState, useRef, useEffect, useCallback } from 'react';
import api, { confirmCommand } from '../api/client';
import useStore from '../store/useStore';
import VoiceOrb from '../components/VoiceOrb';
import './ChatPage.css';

// Suggestions chia theo role
const OWNER_SUGGESTIONS = [
  { icon: '💡', text: 'Bật đèn phòng ngủ' },
  { icon: '🌡', text: 'Nhiệt độ phòng' },
  { icon: '🔒', text: 'Khóa cửa' },
  { icon: '🕐', text: 'Mấy giờ rồi' },
  { icon: '❄️', text: 'Tắt điều hoà' },
  { icon: '❓', text: 'Bạn là ai' },
  { icon: '📞', text: 'Gọi cho 0901234567' },
  { icon: '💙', text: 'Mở Zalo' },
  { icon: '🎵', text: 'Mở Spotify' },
  { icon: '🌐', text: 'Tìm kiếm thời tiết hôm nay' },
];

const GUEST_SUGGESTIONS = [
  { icon: '💡', text: 'Bật đèn phòng khách' },
  { icon: '🌡', text: 'Nhiệt độ phòng' },
  { icon: '🕐', text: 'Mấy giờ rồi' },
  { icon: '👋', text: 'Xin chào' },
];

export default function ChatPage() {
  const { messages, addMessage, roles, pendingConfirm, setPendingConfirm, location, requestLocation } = useStore();
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [speakText, setSpeakText] = useState('');
  const [lastResponse, setLastResponse] = useState(null);
  const [mode, setMode] = useState('voice');
  const historyEndRef = useRef(null);

  const isOwner = roles.includes('owner');
  const SUGGESTIONS = isOwner ? OWNER_SUGGESTIONS : GUEST_SUGGESTIONS;

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Xin quyền GPS khi mount
  useEffect(() => {
    requestLocation();
  }, [requestLocation]);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    addMessage({ role: 'user', text: text.trim() });
    setInput('');
    setIsThinking(true);
    setLastResponse(null);
    setPendingConfirm(null);

    try {
      const payload = { message: text.trim() };
      // Đính kèm vị trí GPS nếu có
      if (location) {
        payload.lat = location.lat;
        payload.lng = location.lng;
      }
      const { data } = await api.post('/chat', payload);
      const aiMsg = {
        role: 'ai',
        text: data.response,
        success: data.success,
        category: data.category || 'general',
        command: data.command,
        requires_confirmation: data.requires_confirmation,
        request_id: data.request_id,
      };
      addMessage(aiMsg);
      setLastResponse(aiMsg);
      setSpeakText(data.response);

      // Nếu cần xác nhận → lưu pending
      if (data.requires_confirmation && data.request_id) {
        setPendingConfirm({
          request_id: data.request_id,
          command: data.command,
          message: data.response,
        });
      }

      // App Action: nếu server đã thực thi → KHÔNG mở tab mới
      // Chỉ fallback window.open nếu server trả web_url nhưng chưa execute
      if (data.command?.data?.web_url && !data.command?.data?.executed_on_server) {
        const webUrl = data.command.data.web_url;
        if (webUrl && !data.command.data?.requires_native) {
          setTimeout(() => {
            window.open(webUrl, '_blank');
          }, 600);
        }
      }
    } catch (err) {
      const errMsg = {
        role: 'ai',
        text: err.response?.status === 401
          ? 'Phiên đăng nhập đã hết hạn. Đang chuyển về trang đăng nhập...'
          : 'Có lỗi kết nối. Vui lòng thử lại.',
        success: false,
      };
      addMessage(errMsg);
      setLastResponse(errMsg);
    } finally {
      setIsThinking(false);
    }
  }, [addMessage, setPendingConfirm]);

  const handleConfirm = useCallback(async (confirmed) => {
    if (!pendingConfirm) return;
    setIsThinking(true);

    try {
      const data = await confirmCommand(pendingConfirm.request_id, confirmed);
      const msg = {
        role: 'ai',
        text: data.response,
        success: data.success,
        category: 'smart_home',
      };
      addMessage(msg);
      setLastResponse(msg);
      setSpeakText(data.response);
    } catch (err) {
      addMessage({ role: 'ai', text: 'Lỗi xác nhận. Thử lại.', success: false });
    } finally {
      setPendingConfirm(null);
      setIsThinking(false);
    }
  }, [pendingConfirm, addMessage, setPendingConfirm]);

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
      location_query: '📍 Vị trí',
      app_action: '⚙️ Ứng dụng',
    };
    return labels[cat] || '💬 Trả lời';
  };

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

        {/* ── Confirmation Modal ─────────────── */}
        {pendingConfirm && !isThinking && (
          <div className="confirm-modal">
            <p className="confirm-modal__text">⚠️ {pendingConfirm.message}</p>
            <div className="confirm-modal__actions">
              <button className="confirm-btn confirm-btn--yes" onClick={() => handleConfirm(true)}>
                ✅ Xác nhận
              </button>
              <button className="confirm-btn confirm-btn--no" onClick={() => handleConfirm(false)}>
                ❌ Huỷ bỏ
              </button>
            </div>
          </div>
        )}

        {/* Suggestions */}
        {!isThinking && !lastResponse && !pendingConfirm && (
          <div className="siri-suggestions">
            {SUGGESTIONS.map((s, i) => (
              <button key={i} className="siri-chip"
                onClick={() => sendMessage(s.text)} disabled={isThinking}>
                {s.icon} {s.text}
              </button>
            ))}
          </div>
        )}

        {/* Suggestions lại sau response */}
        {lastResponse && !isThinking && !pendingConfirm && (
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
