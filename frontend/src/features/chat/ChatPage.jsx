import { useState, useRef, useEffect, useCallback } from 'react'
import { streamMessage, confirmCommand } from '../../api/client'
import useStore from '../../store/useStore'
import VoiceOrb from '../../components/OrbAvatar/OrbAvatar'
import useWakeWord from '../../hooks/useWakeWord'
import { Button, Card, Pill, useToast } from '../../ui'
import './ChatPage.css'

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
]

const GUEST_SUGGESTIONS = [
  { icon: '💡', text: 'Bật đèn phòng khách' },
  { icon: '🌡', text: 'Nhiệt độ phòng' },
  { icon: '🕐', text: 'Mấy giờ rồi' },
  { icon: '👋', text: 'Xin chào' },
]

const CATEGORY_LABEL = {
  smart_home:     '🏠 Nhà thông minh',
  time_query:     '🕐 Thời gian',
  greeting:       '👋 Chào hỏi',
  self_intro:     '🤖 Giới thiệu',
  general_chat:   '💬 Hội thoại',
  dangerous:      '🛡️ Bảo mật',
  thanks:         '💖 Cảm ơn',
  goodbye:        '👋 Tạm biệt',
  compliment:     '🥰 Khen ngợi',
  location_query: '📍 Vị trí',
  app_action:     '⚙️ Ứng dụng',
}

export default function ChatPage() {
  const {
    messages, addMessage, updateLastMessage,
    roles, pendingConfirm, setPendingConfirm,
    location, requestLocation,
  } = useStore()

  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [speakText, setSpeakText] = useState('')
  const [lastResponse, setLastResponse] = useState(null)
  const [mode, setMode] = useState('voice')
  const historyEndRef = useRef(null)
  const toast = useToast()

  // Wake-word "Hey Aisha"
  const voiceOrbRef = useRef(null)
  const [voiceState, setVoiceState] = useState('idle')
  const [wakeEnabled, setWakeEnabled] = useState(() => {
    return localStorage.getItem('aisha:wakeword') === '1'
  })
  const toggleWake = useCallback(() => {
    setWakeEnabled((v) => {
      const next = !v
      localStorage.setItem('aisha:wakeword', next ? '1' : '0')
      return next
    })
  }, [])

  const handleWake = useCallback(() => {
    if (mode !== 'voice') setMode('voice')
    setTimeout(() => {
      voiceOrbRef.current?.startListening?.()
    }, 50)
  }, [mode])

  const wakePaused = voiceState === 'listening' || voiceState === 'speaking' || isThinking
  const { active: wakeActive, supported: wakeSupported, error: wakeError } = useWakeWord({
    enabled: wakeEnabled,
    paused: wakePaused,
    onWake: handleWake,
  })

  const isOwner = roles.includes('owner')
  const SUGGESTIONS = isOwner ? OWNER_SUGGESTIONS : GUEST_SUGGESTIONS

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    requestLocation()
  }, [requestLocation])

  const abortRef = useRef(null)

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return

    if (abortRef.current) {
      try { abortRef.current.abort() } catch { /* ignore */ }
      abortRef.current = null
    }
    const controller = new AbortController()
    abortRef.current = controller

    const userText = text.trim()
    addMessage({ role: 'user', text: userText })
    setInput('')
    setIsThinking(true)
    setLastResponse(null)
    setPendingConfirm(null)

    addMessage({ role: 'ai', text: '', streaming: true, category: 'general_chat' })

    let accumText = ''
    let currentCategory = 'general_chat'
    let currentRequestId = null

    try {
      await streamMessage(userText, {
        lat: location?.lat ?? null,
        lng: location?.lng ?? null,
        signal: controller.signal,
        onMeta: (m) => {
          currentCategory = m.category || 'general_chat'
          currentRequestId = m.request_id || null
          setIsThinking(false)
          updateLastMessage({ category: currentCategory, request_id: currentRequestId })
        },
        onChunk: (piece) => {
          if (!piece) return
          accumText += piece
          updateLastMessage({ text: accumText })
          setLastResponse({
            role: 'ai',
            text: accumText,
            category: currentCategory,
            streaming: true,
          })
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
          }
          updateLastMessage(finalMsg)
          setLastResponse(finalMsg)
          if (finalMsg.success && accumText) setSpeakText(accumText)

          if (d.requires_confirmation && d.request_id) {
            setPendingConfirm({
              request_id: d.request_id,
              command: d.command,
              message: accumText,
            })
          }

          if (d.command?.data?.web_url && !d.command?.data?.executed_on_server) {
            const webUrl = d.command.data.web_url
            if (webUrl && !d.command.data?.requires_native) {
              setTimeout(() => { window.open(webUrl, '_blank') }, 600)
            }
          }
        },
        onError: (err) => {
          console.error('[Chat:Stream] error:', err)
        },
      })
    } catch (err) {
      if (err?.name === 'AbortError' || controller.signal.aborted) return
      const errMsg = {
        role: 'ai',
        text: err?.status === 401
          ? 'Phiên đăng nhập đã hết hạn. Đang chuyển về trang đăng nhập…'
          : 'Có lỗi kết nối. Vui lòng thử lại.',
        success: false,
        streaming: false,
        category: currentCategory,
      }
      updateLastMessage(errMsg)
      setLastResponse(errMsg)
      toast.error(errMsg.text)
    } finally {
      setIsThinking(false)
      if (abortRef.current === controller) abortRef.current = null
    }
  }, [addMessage, updateLastMessage, setPendingConfirm, location, toast])

  useEffect(() => {
    return () => {
      if (abortRef.current) {
        try { abortRef.current.abort() } catch { /* ignore */ }
      }
    }
  }, [])

  const handleConfirm = useCallback(async (confirmed) => {
    if (!pendingConfirm) return
    setIsThinking(true)
    try {
      const data = await confirmCommand(pendingConfirm.request_id, confirmed)
      const msg = {
        role: 'ai',
        text: data.response,
        success: data.success,
        category: 'smart_home',
      }
      addMessage(msg)
      setLastResponse(msg)
      setSpeakText(data.response)
    } catch {
      const errText = 'Lỗi xác nhận, hãy thử lại.'
      addMessage({ role: 'ai', text: errText, success: false })
      toast.error(errText)
    } finally {
      setPendingConfirm(null)
      setIsThinking(false)
    }
  }, [pendingConfirm, addMessage, setPendingConfirm, toast])

  const handleVoiceResult = useCallback((text) => sendMessage(text), [sendMessage])
  const handleSpeakEnd = useCallback(() => setSpeakText(''), [])

  const handleSubmit = (e) => {
    e.preventDefault()
    sendMessage(input)
  }

  const historyMessages = messages.filter(m => m.id !== 'welcome').slice(0, -2)

  return (
    <div className="chat-page">
      {/* ── Mode toolbar ─────────────────────── */}
      <div className="chat-toolbar">
        <div className="chat-segment" role="tablist" aria-label="Chế độ nhập">
          <button
            className={`chat-segment__btn ${mode === 'voice' ? 'is-active' : ''}`}
            onClick={() => setMode('voice')}
            role="tab"
            aria-selected={mode === 'voice'}
          >
            <MicIcon /> Giọng nói
          </button>
          <button
            className={`chat-segment__btn ${mode === 'text' ? 'is-active' : ''}`}
            onClick={() => setMode('text')}
            role="tab"
            aria-selected={mode === 'text'}
          >
            <KeyboardIcon /> Văn bản
          </button>
        </div>

        <button
          className={`chat-wake-btn ${wakeEnabled ? 'is-on' : ''} ${wakeActive ? 'is-listening' : ''}`}
          onClick={toggleWake}
          disabled={!wakeSupported}
          title={
            !wakeSupported
              ? 'Trình duyệt không hỗ trợ wake-word'
              : wakeEnabled
              ? `Hey Aisha ${wakeActive ? '· đang nghe' : ''}`
              : 'Bật để kích hoạt khi nói "Hey Aisha"'
          }
          aria-pressed={wakeEnabled}
        >
          <span className="chat-wake-btn__dot" data-state={wakeEnabled ? (wakeActive ? 'live' : 'idle-on') : 'off'} />
          Hey Aisha
        </button>
      </div>
      {wakeEnabled && wakeError && (
        <div className="chat-wake-error">⚠ Wake-word: {wakeError}</div>
      )}

      {/* ── Voice / Response Stage ───────────── */}
      <section className="chat-stage">
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

        {/* Thinking dots */}
        {isThinking && (
          <Card variant="glass" className="chat-response chat-response--thinking">
            <div className="chat-thinking">
              <span /><span /><span />
            </div>
          </Card>
        )}

        {/* AI response */}
        {lastResponse && !isThinking && (
          <Card variant="glass" className="chat-response">
            <p className="chat-response__text">
              {lastResponse.text}
              {lastResponse.streaming && <span className="chat-response__cursor">▍</span>}
            </p>
            <div className="chat-response__meta">
              <Pill tone="brand" size="sm">
                {CATEGORY_LABEL[lastResponse.category] || '💬 Trả lời'}
              </Pill>
              {!lastResponse.streaming && lastResponse.success !== undefined && (
                <Pill tone={lastResponse.success ? 'success' : 'danger'} size="sm">
                  {lastResponse.success ? '✓ OK' : '✕ Lỗi'}
                </Pill>
              )}
            </div>
          </Card>
        )}

        {/* Confirmation */}
        {pendingConfirm && !isThinking && (
          <Card variant="aurora" className="chat-confirm">
            <p className="chat-confirm__text">
              <span className="chat-confirm__icon" aria-hidden>⚠️</span>
              {pendingConfirm.message}
            </p>
            <div className="chat-confirm__actions">
              <Button variant="primary" onClick={() => handleConfirm(true)}>
                ✓ Xác nhận
              </Button>
              <Button variant="ghost" onClick={() => handleConfirm(false)}>
                Huỷ bỏ
              </Button>
            </div>
          </Card>
        )}

        {/* Suggestions */}
        {!isThinking && !pendingConfirm && (
          <div className="chat-suggestions">
            {(lastResponse ? SUGGESTIONS.slice(0, 4) : SUGGESTIONS).map((s, i) => (
              <button
                key={i}
                className="chat-chip"
                onClick={() => {
                  if (lastResponse) setLastResponse(null)
                  sendMessage(s.text)
                }}
                disabled={isThinking}
              >
                <span className="chat-chip__icon">{s.icon}</span>
                <span className="chat-chip__text">{s.text}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ── Mini history ─────────────────────── */}
      {historyMessages.length > 0 && (
        <div className="chat-history">
          {historyMessages.map((msg, i) => (
            <div key={i} className={`chat-bubble chat-bubble--${msg.role}`}>
              {msg.text?.length > 80 ? msg.text.slice(0, 80) + '…' : msg.text}
            </div>
          ))}
          <div ref={historyEndRef} />
        </div>
      )}

      {/* ── Composer ─────────────────────────── */}
      <form className="chat-composer" onSubmit={handleSubmit}>
        <input
          type="text"
          className="chat-composer__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Hỏi Aisha bất cứ điều gì…"
          disabled={isThinking}
          aria-label="Nhập tin nhắn"
        />
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={!input.trim() || isThinking}
          loading={isThinking}
          aria-label="Gửi"
        >
          <SendIcon />
        </Button>
      </form>
    </div>
  )
}

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="12" rx="3"/>
      <path d="M5 10v2a7 7 0 0 0 14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
    </svg>
  )
}
function KeyboardIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="12" rx="2"/>
      <line x1="6" y1="10" x2="6" y2="10"/>
      <line x1="10" y1="10" x2="10" y2="10"/>
      <line x1="14" y1="10" x2="14" y2="10"/>
      <line x1="18" y1="10" x2="18" y2="10"/>
      <line x1="7" y1="14" x2="17" y2="14"/>
    </svg>
  )
}
function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13"/>
      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  )
}
