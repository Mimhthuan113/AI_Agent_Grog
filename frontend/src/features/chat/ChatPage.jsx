import { useState, useRef, useEffect, useCallback } from 'react'
import { streamMessage, confirmCommand, stopAutomation, getAutomationStatus } from '../../api/client'
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

const WAKE_PROMPT = 'Bạn cần gì?'
const QUICK_SPEAK_MIN_CHARS = 10
const QUICK_SPEAK_FALLBACK_CHARS = 80
const QUICK_SPEAK_MAX_CHARS = 130
const QUICK_SPEAK_CATEGORIES = new Set(['general_chat', 'app_action', 'smart_home'])

function extractQuickSpeakText(text) {
  const clean = (text || '').replace(/\s+/g, ' ').trim()
  if (clean.length < QUICK_SPEAK_MIN_CHARS) return ''
  const sentence = clean.match(/^(.{10,130}?[.!?…])(?:\s|$)/)
  if (sentence?.[1]) return sentence[1].trim()
  if (clean.length >= QUICK_SPEAK_FALLBACK_CHARS) {
    return clean.slice(0, QUICK_SPEAK_MAX_CHARS).replace(/\s+\S*$/, '').trim()
  }
  return ''
}

function getRemainingSpeech(fullText, spokenPrefix) {
  const full = (fullText || '').replace(/\s+/g, ' ').trim()
  const spoken = (spokenPrefix || '').replace(/\s+/g, ' ').trim()
  if (!full || !spoken || !full.startsWith(spoken)) return ''
  return full.slice(spoken.length).replace(/^[\s,.;:!?…-]+/, '').trim()
}

export default function ChatPage() {
  const {
    messages, addMessage, updateLastMessage,
    roles, pendingConfirm, setPendingConfirm,
    location, requestLocation,
  } = useStore()

  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [isAutomating, setIsAutomating] = useState(false)  // UI Agent dang chay
  const [speakText, setSpeakText] = useState('')
  const [lastResponse, setLastResponse] = useState(null)
  const [mode, setMode] = useState('voice')
  const historyEndRef = useRef(null)
  const toast = useToast()
  const automationPollRef = useRef(null)

  // Wake-word "Hey Aisha"
  const voiceOrbRef = useRef(null)
  const wakePromptPendingRef = useRef(false)
  const wakeConversationRef = useRef(false)
  const modeRef = useRef(mode)
  const isThinkingRef = useRef(isThinking)
  const isAutomatingRef = useRef(isAutomating)
  const isRespondingRef = useRef(false)
  const quickSpeakStartedRef = useRef(false)
  const spokenPrefixRef = useRef('')
  const pendingSpeakTextRef = useRef('')
  const [voiceState, setVoiceState] = useState('idle')
  const voiceStateRef = useRef(voiceState)
  const [wakeEnabled, setWakeEnabled] = useState(true)

  useEffect(() => { modeRef.current = mode }, [mode])
  useEffect(() => { isThinkingRef.current = isThinking }, [isThinking])
  useEffect(() => { isAutomatingRef.current = isAutomating }, [isAutomating])
  useEffect(() => { voiceStateRef.current = voiceState }, [voiceState])
  useEffect(() => { localStorage.setItem('aisha:wakeword', '1') }, [])

  const toggleWake = useCallback(() => {
    setWakeEnabled((v) => {
      const next = !v
      localStorage.setItem('aisha:wakeword', next ? '1' : '0')
      if (!next) {
        wakePromptPendingRef.current = false
        wakeConversationRef.current = false
      }
      return next
    })
  }, [])

  const startListeningSoon = useCallback((delay = 160) => {
    window.setTimeout(() => {
      voiceOrbRef.current?.startListening?.({ force: true })
    }, delay)
  }, [])

  const handleWake = useCallback(() => {
    if (isThinkingRef.current || isAutomatingRef.current) return
    if (mode !== 'voice') setMode('voice')
    wakeConversationRef.current = true
    wakePromptPendingRef.current = true
    setLastResponse({
      role: 'ai',
      text: WAKE_PROMPT,
      success: true,
      category: 'greeting',
      streaming: false,
    })
    setSpeakText('')
    setTimeout(() => {
      setSpeakText(WAKE_PROMPT)
    }, 30)
  }, [mode])

  const wakePaused = voiceState === 'listening' || voiceState === 'speaking' || isThinking || isAutomating
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
    isRespondingRef.current = true
    quickSpeakStartedRef.current = false
    spokenPrefixRef.current = ''
    pendingSpeakTextRef.current = ''
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
          // Neu la app_action thi bat dau poll automation status
          if (currentCategory === 'app_action') {
            setIsAutomating(true)
            startAutomationPolling()
          }
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
          if (!quickSpeakStartedRef.current && QUICK_SPEAK_CATEGORIES.has(currentCategory)) {
            const quickText = extractQuickSpeakText(accumText)
            if (quickText) {
              quickSpeakStartedRef.current = true
              spokenPrefixRef.current = quickText
              setSpeakText('')
              setTimeout(() => setSpeakText(quickText), 0)
            }
          }
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
          if (currentCategory === 'goodbye') {
            wakeConversationRef.current = false
          }
          if (finalMsg.success && accumText) {
            if (quickSpeakStartedRef.current) {
              const remaining = getRemainingSpeech(accumText, spokenPrefixRef.current)
              if (remaining.length >= QUICK_SPEAK_MIN_CHARS) {
                if (voiceStateRef.current === 'speaking') {
                  pendingSpeakTextRef.current = remaining
                } else {
                  setSpeakText('')
                  setTimeout(() => setSpeakText(remaining), 40)
                }
              }
            } else {
              setSpeakText(accumText)
            }
          }

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
          isRespondingRef.current = false
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
      isRespondingRef.current = false
      setIsThinking(false)
      setIsAutomating(false)
      stopAutomationPolling()
      if (abortRef.current === controller) abortRef.current = null
    }
  }, [addMessage, updateLastMessage, setPendingConfirm, location, toast])

  useEffect(() => {
    return () => {
      if (abortRef.current) {
        try { abortRef.current.abort() } catch { /* ignore */ }
      }
      stopAutomationPolling()
    }
  }, [])

  // Poll automation status moi 1.5s
  const startAutomationPolling = useCallback(() => {
    stopAutomationPolling()
    automationPollRef.current = setInterval(async () => {
      try {
        const { running } = await getAutomationStatus()
        if (!running) {
          setIsAutomating(false)
          stopAutomationPolling()
        }
      } catch {
        setIsAutomating(false)
        stopAutomationPolling()
      }
    }, 1500)
  }, [])

  const stopAutomationPolling = useCallback(() => {
    if (automationPollRef.current) {
      clearInterval(automationPollRef.current)
      automationPollRef.current = null
    }
  }, [])

  const handleStopAutomation = useCallback(async () => {
    try {
      await stopAutomation()
      setIsAutomating(false)
      stopAutomationPolling()
      toast.info('Đã gửi lệnh dừng tự động hóa.')
    } catch {
      toast.error('Không thể dừng tự động hóa. Thử lại.')
    }
  }, [stopAutomationPolling, toast])

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
  const handleSpeakEnd = useCallback(() => {
    const shouldListenAfterWakePrompt = wakePromptPendingRef.current
    wakePromptPendingRef.current = false
    setSpeakText('')

    const pendingSpeech = pendingSpeakTextRef.current
    if (pendingSpeech) {
      pendingSpeakTextRef.current = ''
      setTimeout(() => setSpeakText(pendingSpeech), 60)
      return
    }

    if (isRespondingRef.current) return

    if (shouldListenAfterWakePrompt) {
      startListeningSoon(180)
      return
    }

    if (
      wakeConversationRef.current
      && modeRef.current === 'voice'
      && !isThinkingRef.current
      && !isAutomatingRef.current
    ) {
      startListeningSoon(260)
    }
  }, [startListeningSoon])

  const handleSubmit = (e) => {
    e.preventDefault()
    sendMessage(input)
  }

  const historyMessages = messages.filter(m => m.id !== 'welcome').slice(0, -2)

  return (
    <div className="chat-page">

      {/* ── Automation Overlay — chặn user khi UI Agent đang chạy ── */}
      {isAutomating && (
        <div className="automation-overlay" role="alertdialog" aria-label="Đang tự động hóa">
          <div className="automation-overlay__box">
            <div className="automation-overlay__ring">
              <div className="automation-overlay__spinner" />
              <span className="automation-overlay__icon" aria-hidden>&#129302;</span>
            </div>
            <p className="automation-overlay__title">Đang tự động hóa…</p>
            <p className="automation-overlay__sub">
              Aisha đang điều khiển máy tính của bạn.<br />
              Vui lòng đợi và không can thiệp.
            </p>
            <div className="automation-overlay__hint">
              <span>⏸</span> Nhấn nút bên dưới để dừng khẩn cấp
            </div>
            <button
              className="automation-overlay__stop"
              onClick={handleStopAutomation}
            >
              ⏹️ Dừng ngay
            </button>
          </div>
        </div>
      )}

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
            onClick={() => {
              wakeConversationRef.current = false
              wakePromptPendingRef.current = false
              setMode('text')
            }}
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
