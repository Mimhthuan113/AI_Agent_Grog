import { useState, useRef, useEffect, useCallback } from 'react';
import { streamMessage, confirmCommand } from '../api/client';
import useStore from '../store/useStore';
import VoiceOrb from '../components/VoiceOrb';
import useWakeWord from '../hooks/useWakeWord';
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
  const {
    messages, addMessage, updateLastMessage,
    roles, pendingConfirm, setPendingConfirm,
    location, requestLocation,
  } = useStore();
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [speakText, setSpeakText] = useState('');
  const [lastResponse, setLastResponse] = useState(null);
  const [mode, setMode] = useState('voice');
  const historyEndRef = useRef(null);

  // Wake-word "Hey Aisha"
  const voiceOrbRef = useRef(null);
  const [voiceState, setVoiceState] = useState('idle');
  const [wakeEnabled, setWakeEnabled] = useState(() => {
    return localStorage.getItem('aisha:wakeword') === '1';
  });
  const toggleWake = useCallback(() => {
    setWakeEnabled((v) => {
      const next = !v;
      localStorage.setItem('aisha:wakeword', next ? '1' : '0');
      return next;
    });
  }, []);

  const handleWake = useCallback(() => {
    // Tự chuyển sang mode voice nếu đang ở text (giúp orb hiển thị)
    if (mode !== 'voice') setMode('voice');
    // Defer 1 frame để VoiceOrb mount xong nếu vừa đổi mode
    setTimeout(() => {
      voiceOrbRef.current?.startListening?.();
    }, 50);
  }, [mode]);

  // Pause wake-word khi orb đang nghe / đang nói (tránh tranh chấp mic)
  // hoặc khi đang xử lý request.
  const wakePaused = voiceState === 'listening' || voiceState === 'speaking' || isThinking;
  const { active: wakeActive, supported: wakeSupported, error: wakeError } = useWakeWord({
    enabled: wakeEnabled,
    paused: wakePaused,
    onWake: handleWake,
  });

  const isOwner = roles.includes('owner');
  const SUGGESTIONS = isOwner ? OWNER_SUGGESTIONS : GUEST_SUGGESTIONS;

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Xin quyền GPS khi mount
  useEffect(() => {
    requestLocation();
  }, [requestLocation]);

  const abortRef = useRef(null);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    // Nếu đang stream → hủy stream cũ trước khi mở mới
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch { /* ignore */ }
      abortRef.current = null;
    }
    const controller = new AbortController();
    abortRef.current = controller;

    const userText = text.trim();
    addMessage({ role: 'user', text: userText });
    setInput('');
    setIsThinking(true);
    setLastResponse(null);
    setPendingConfirm(null);

    // Thêm placeholder AI để stream cập nhật dần
    addMessage({ role: 'ai', text: '', streaming: true, category: 'general_chat' });

    let accumText = '';
    let currentCategory = 'general_chat';
    let currentRequestId = null;

    try {
      await streamMessage(userText, {
        lat: location?.lat ?? null,
        lng: location?.lng ?? null,
        signal: controller.signal,
        onMeta: (m) => {
          currentCategory = m.category || 'general_chat';
          currentRequestId = m.request_id || null;
          // Có meta → bắt đầu render text dần, ẩn thinking dots
          setIsThinking(false);
          updateLastMessage({ category: currentCategory, request_id: currentRequestId });
        },
        onChunk: (piece) => {
          if (!piece) return;
          accumText += piece;
          updateLastMessage({ text: accumText });
          setLastResponse({
            role: 'ai',
            text: accumText,
            category: currentCategory,
            streaming: true,
          });
        },
        onDone: (d) => {
          const finalMsg = {
            role: 'ai',
            text: accumText,
            success: d.success !== false,
            category: currentCategory,
            command: d.command,
            requires_confirmation: !!d.requires_confirmation,
            request_id: d.request_id || currentRequestId,
            streaming: false,
          };
          updateLastMessage(finalMsg);
          setLastResponse(finalMsg);
          // Chỉ TTS khi response thành công và có nội dung
          if (finalMsg.success && accumText) setSpeakText(accumText);

          // Confirmation flow
          if (d.requires_confirmation && d.request_id) {
            setPendingConfirm({
              request_id: d.request_id,
              command: d.command,
              message: accumText,
            });
          }

          // App Action fallback web_url
          if (d.command?.data?.web_url && !d.command?.data?.executed_on_server) {
            const webUrl = d.command.data.web_url;
            if (webUrl && !d.command.data?.requires_native) {
              setTimeout(() => {
                window.open(webUrl, '_blank');
              }, 600);
            }
          }
        },
        onError: (err) => {
          console.error('[Chat:Stream] error:', err);
        },
      });
    } catch (err) {
      // AbortError khi user gửi tin mới → bỏ qua, không hiện lỗi
      if (err?.name === 'AbortError' || controller.signal.aborted) return;
      const errMsg = {
        role: 'ai',
        text: err?.status === 401
          ? 'Phiên đăng nhập đã hết hạn. Đang chuyển về trang đăng nhập...'
          : 'Có lỗi kết nối. Vui lòng thử lại.',
        success: false,
        streaming: false,
        category: currentCategory,
      };
      updateLastMessage(errMsg);
      setLastResponse(errMsg);
    } finally {
      setIsThinking(false);
      // Chỉ clear khi controller này còn là current (không bị stream khác replace)
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [addMessage, updateLastMessage, setPendingConfirm, location]);

  // Cleanup khi unmount: hủy stream nếu còn
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        try { abortRef.current.abort(); } catch { /* ignore */ }
      }
    };
  }, []);

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
    } catch {
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
        <button
          className={`mode-btn wake-btn ${wakeEnabled ? 'active' : ''}`}
          onClick={toggleWake}
          title={
            !wakeSupported
              ? 'Browser không hỗ trợ wake-word (dùng Chrome/Edge)'
              : wakeEnabled
              ? `Wake-word ON${wakeActive ? ' · đang nghe "Hey Aisha"' : ''}`
              : 'Bật để kích hoạt khi nói "Hey Aisha"'
          }
          disabled={!wakeSupported}
        >
          {wakeEnabled ? (wakeActive ? '👂' : '🟡') : '💤'} Hey Aisha
        </button>
      </div>
      {wakeEnabled && wakeError && (
        <div className="wake-error">⚠ Wake-word: {wakeError}</div>
      )}

      {/* ── Siri Center ───────────────────────── */}
      <div className="siri-center">

        {/* Voice Orb */}
        {mode === 'voice' && (
          <VoiceOrb
            ref={voiceOrbRef}
            onResult={handleVoiceResult}
            onSpeakEnd={handleSpeakEnd}
            onStateChange={setVoiceState}
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
          <div className="siri-response">
            <p className="siri-response__text">
              {lastResponse.text}
              {lastResponse.streaming && <span className="siri-cursor">▍</span>}
            </p>
            <div className="siri-response__category">
              {getCategoryLabel(lastResponse.category)}
              {!lastResponse.streaming && lastResponse.success !== undefined && (
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
