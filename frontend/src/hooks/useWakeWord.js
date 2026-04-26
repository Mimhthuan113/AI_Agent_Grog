import { useEffect, useRef, useCallback, useState } from 'react'
import { isCapacitorNative } from '../api/config'

// Các biến thể "Hey Aisha" mà SpeechRecognition tiếng Việt thường nhận
// (Web Speech API không phân biệt chính xác → dùng phrase variants để bắt nhiều cách phát âm)
const DEFAULT_PHRASES = [
  'hey aisha',
  'hi aisha',
  'hey ai sa',
  'hey ai sha',
  'hi ai sha',
  'hi ai sa',
  'hê aisha',
  'hê ai sa',
  'ê aisha',
  'ê ai sa',
  'này aisha',
  'này ai sa',
  'aisha ơi',
  'ai sa ơi',
  'ai sha ơi',
]

/**
 * Hook wake-word "Hey Aisha" — dual backend:
 *   • Native Capacitor → @capacitor-community/speech-recognition (Android SpeechRecognizer)
 *   • Web browser     → Web Speech API (Chrome/Edge)
 *
 * Tự động chọn backend phù hợp dựa vào `isCapacitorNative()`.
 * Cả hai đều auto-restart liên tục để hoạt động dài hạn (Android giới hạn ~10s/session,
 * Chrome ~60s/session).
 *
 * @param {Object} opts
 * @param {string[]} opts.phrases       Các phrase trigger (đã lower-case).
 * @param {(text: string) => void} opts.onWake   Callback khi nhận được wake phrase.
 * @param {boolean} opts.enabled        Bật/tắt hook.
 * @param {boolean} opts.paused         Tạm dừng (vd: khi VoiceOrb đang listening).
 * @param {number} opts.cooldownMs      Khoảng cách tối thiểu giữa 2 lần fire (ms).
 *
 * @returns {{active: boolean, supported: boolean, error: string|null, backend: 'native'|'web'|null}}
 */
export default function useWakeWord({
  phrases = DEFAULT_PHRASES,
  onWake,
  enabled = true,
  paused = false,
  cooldownMs = 2500,
} = {}) {
  // ── Refs (giá trị giữ qua re-render, KHÔNG trigger render khi đổi) ──
  const recogRef = useRef(null)            // Web SpeechRecognition instance
  const nativeListenerRef = useRef(null)   // Native plugin listener handle
  const restartTimerRef = useRef(null)
  const stoppedManuallyRef = useRef(false)
  const onWakeRef = useRef(onWake)
  const phrasesRef = useRef(phrases)
  const lastFireAtRef = useRef(0)
  const lastMatchedTextRef = useRef('')
  const startRef = useRef(null)            // Tránh TDZ khi gọi đệ quy

  const [active, setActive] = useState(false)
  const [supported, setSupported] = useState(true)
  const [error, setError] = useState(null)
  const [backend, setBackend] = useState(null)

  // Sync ref khi prop thay đổi
  useEffect(() => { onWakeRef.current = onWake }, [onWake])
  useEffect(() => { phrasesRef.current = phrases }, [phrases])

  // ── Helper: kiểm tra phrase có match không (chung cho cả 2 backend) ──
  const tryMatch = useCallback((rawText) => {
    const text = (rawText || '').toLowerCase().trim()
    if (!text) return false
    const now = Date.now()
    if (now - lastFireAtRef.current < cooldownMs) return false
    if (text === lastMatchedTextRef.current) return false

    const matched = phrasesRef.current.find((p) => text.includes(p.toLowerCase()))
    if (!matched) return false

    lastFireAtRef.current = now
    lastMatchedTextRef.current = text
    try { onWakeRef.current?.(text) } catch { /* ignore */ }
    return true
  }, [cooldownMs])

  // ── Stop (chung cho 2 backend) ──
  const stop = useCallback(async () => {
    stoppedManuallyRef.current = true
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    // Web backend
    const r = recogRef.current
    if (r) {
      try { r.onend = null } catch { /* ignore */ }
      try { r.stop() } catch { /* ignore */ }
      recogRef.current = null
    }
    // Native backend
    if (nativeListenerRef.current) {
      try { await nativeListenerRef.current.remove() } catch { /* ignore */ }
      nativeListenerRef.current = null
      try {
        const { SpeechRecognition } = await import('@capacitor-community/speech-recognition')
        await SpeechRecognition.stop()
      } catch { /* ignore */ }
    }
    setActive(false)
  }, [])

  // ── Web backend (Chrome/Edge) ──
  const startWeb = useCallback(() => {
    setBackend('web')
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setSupported(false)
      setError('Browser không hỗ trợ Web Speech API. Dùng Chrome/Edge để bật wake-word.')
      return
    }
    setSupported(true)
    if (recogRef.current) return // đã chạy

    const rec = new SR()
    rec.lang = 'vi-VN'
    rec.continuous = true
    rec.interimResults = true
    rec.maxAlternatives = 1

    rec.onstart = () => { setActive(true); setError(null) }
    rec.onerror = (e) => {
      // no-speech / aborted lặp lại liên tục, bỏ qua
      if (e.error && e.error !== 'no-speech' && e.error !== 'aborted') {
        setError(e.error)
      }
    }
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i]
        if (tryMatch(r[0]?.transcript)) return
      }
    }
    rec.onend = () => {
      setActive(false)
      recogRef.current = null
      if (!stoppedManuallyRef.current) {
        restartTimerRef.current = setTimeout(() => startRef.current?.(), 250)
      }
    }

    recogRef.current = rec
    stoppedManuallyRef.current = false
    try {
      rec.start()
    } catch (err) {
      setError(err?.message || 'start failed')
      recogRef.current = null
    }
  }, [tryMatch])

  // ── Native backend (Capacitor plugin) ──
  const startNative = useCallback(async () => {
    setBackend('native')
    let SpeechRecognition
    try {
      ({ SpeechRecognition } = await import('@capacitor-community/speech-recognition'))
    } catch (e) {
      setSupported(false)
      setError('Không tải được plugin speech-recognition: ' + (e?.message || ''))
      return
    }

    // Check available + permission
    try {
      const { available } = await SpeechRecognition.available()
      if (!available) {
        setSupported(false)
        setError('Thiết bị không hỗ trợ SpeechRecognizer.')
        return
      }
      const perm = await SpeechRecognition.checkPermissions()
      if (perm.permission !== 'granted') {
        const req = await SpeechRecognition.requestPermissions()
        if (req.permission !== 'granted') {
          setSupported(false)
          setError('Bạn cần cấp quyền micro để dùng wake-word.')
          return
        }
      }
    } catch (e) {
      setError('Lỗi kiểm tra quyền: ' + (e?.message || e))
      return
    }

    setSupported(true)

    // Đăng ký listener trước khi start
    try {
      // Listener trả về object có method remove()
      nativeListenerRef.current = await SpeechRecognition.addListener(
        'partialResults',
        (data) => {
          const matches = data?.matches || []
          for (const text of matches) {
            if (tryMatch(text)) return
          }
        },
      )
    } catch (e) {
      setError('Không gắn listener: ' + (e?.message || e))
      return
    }

    // Start (Android tự dừng sau ~10s → restart trong onend)
    stoppedManuallyRef.current = false
    try {
      await SpeechRecognition.start({
        language: 'vi-VN',
        maxResults: 1,
        prompt: '',
        partialResults: true,
        popup: false,
      })
      setActive(true)
      setError(null)

      // Plugin v6 không có event 'onEnd' chính thức trên Android — dùng polling
      // SpeechRecognition.isListening() để biết đã dừng hay chưa, restart liên tục
      const watchdog = async () => {
        if (stoppedManuallyRef.current) return
        try {
          const { listening } = await SpeechRecognition.isListening()
          if (!listening) {
            setActive(false)
            // Restart sau 300ms
            restartTimerRef.current = setTimeout(() => startRef.current?.(), 300)
            return
          }
        } catch { /* ignore */ }
        restartTimerRef.current = setTimeout(watchdog, 1000)
      }
      restartTimerRef.current = setTimeout(watchdog, 1000)
    } catch (e) {
      setError('Không khởi động được: ' + (e?.message || e))
      setActive(false)
    }
  }, [tryMatch])

  // ── Dispatcher ──
  const start = useCallback(() => {
    if (isCapacitorNative()) {
      startNative()
    } else {
      startWeb()
    }
  }, [startWeb, startNative])

  // Đồng bộ ref `startRef` để onend / watchdog gọi qua ref tránh TDZ
  useEffect(() => { startRef.current = start }, [start])

  // Sync enabled / paused → start / stop
  useEffect(() => {
    if (enabled && !paused) {
      start()
    } else {
      stop()
    }
    return () => { stop() }
  }, [enabled, paused, start, stop])

  return { active, supported, error, backend }
}
