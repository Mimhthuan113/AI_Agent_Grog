import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import './Toast.css'

const ToastCtx = createContext(null)

const ICONS = {
  success: '✓',
  warn:    '!',
  danger:  '✕',
  info:    'i',
}

let _id = 0
const nextId = () => ++_id

/**
 * Provider toast — đặt ở root App.
 * Dùng useToast() hook để trigger từ bất kỳ component nào.
 */
export function ToastProvider({ children, position = 'top-center' }) {
  const [toasts, setToasts] = useState([])
  const timersRef = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id))
    const tm = timersRef.current.get(id)
    if (tm) { clearTimeout(tm); timersRef.current.delete(id) }
  }, [])

  const show = useCallback((opts) => {
    const id = nextId()
    const toast = {
      id,
      tone: opts.tone || 'info',
      title: opts.title || '',
      message: opts.message || '',
      duration: opts.duration ?? 4000,
    }
    setToasts((list) => [...list, toast])
    if (toast.duration > 0) {
      const tm = setTimeout(() => dismiss(id), toast.duration)
      timersRef.current.set(id, tm)
    }
    return id
  }, [dismiss])

  // Cleanup timers on unmount
  useEffect(() => () => {
    timersRef.current.forEach((tm) => clearTimeout(tm))
    timersRef.current.clear()
  }, [])

  const api = useMemo(() => ({
    show,
    dismiss,
    success: (msg, opts) => show({ ...opts, tone: 'success', message: msg }),
    info:    (msg, opts) => show({ ...opts, tone: 'info',    message: msg }),
    warn:    (msg, opts) => show({ ...opts, tone: 'warn',    message: msg }),
    error:   (msg, opts) => show({ ...opts, tone: 'danger',  message: msg }),
  }), [show, dismiss])

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div className={`ai-toast-stack ai-toast-stack--${position}`} role="region" aria-label="Thông báo">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`ai-toast ai-toast--${t.tone}`}
            role={t.tone === 'danger' ? 'alert' : 'status'}
          >
            <span className="ai-toast__icon" aria-hidden>{ICONS[t.tone]}</span>
            <div className="ai-toast__body">
              {t.title && <strong className="ai-toast__title">{t.title}</strong>}
              {t.message && <span className="ai-toast__msg">{t.message}</span>}
            </div>
            <button
              className="ai-toast__close"
              onClick={() => dismiss(t.id)}
              aria-label="Đóng thông báo"
            >×</button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
