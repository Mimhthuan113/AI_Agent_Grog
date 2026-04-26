import { useState, useEffect, useRef } from 'react'
import { login as apiLogin, googleLogin as apiGoogleLogin, getMe } from '../api/client'
import useStore from '../store/useStore'
import './LoginPage.css'

// Google Client ID — đọc từ env (VITE_GOOGLE_CLIENT_ID), fallback dev local
const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  '1024198635802-ke42fatp2odl6coh5ploporrd62qcnve.apps.googleusercontent.com'

// Prefill chỉ khi DEV mode (để debug nhanh). Production luôn rỗng.
const DEV_PREFILL = import.meta.env.DEV
  ? { username: 'admin', password: 'changeme_strong_password_here' }
  : { username: '', password: '' }

export default function LoginPage() {
  const [username, setUsername] = useState(DEV_PREFILL.username)
  const [password, setPassword] = useState(DEV_PREFILL.password)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setAuth = useStore(s => s.setAuth)
  const googleBtnRef = useRef(null)

  // Load Google Identity Services script
  useEffect(() => {
    // Kiểm tra script đã load chưa
    if (window.google?.accounts?.id) {
      initGoogleButton()
      return
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => initGoogleButton()
    document.head.appendChild(script)

    return () => {
      // Cleanup nếu cần
    }
  }, [])

  const initGoogleButton = () => {
    if (!window.google?.accounts?.id || !googleBtnRef.current) return

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleCallback,
      auto_select: false,
    })

    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'filled_black',
      shape: 'pill',
      size: 'large',
      width: 310,
      text: 'signin_with',
      locale: 'vi',
    })
  }

  const handleLogin = async () => {
    setError('')
    setLoading(true)
    try {
      const data = await apiLogin(username, password)
      setAuth({ user_id: data.user_id }, data.access_token)
    } catch (e) {
      setError(e.response?.data?.detail || 'Không kết nối được server')
    }
    setLoading(false)
  }

  const handleGoogleCallback = async (response) => {
    setError('')
    setLoading(true)
    try {
      const data = await apiGoogleLogin(response.credential)
      // Lấy roles từ /auth/me
      const me = await getMe()
      setAuth(me, data.access_token)
    } catch (e) {
      setError(e.response?.data?.detail || 'Đăng nhập Google thất bại')
    }
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="gradient-orb orb-1" style={{ animation: 'orbFloat 8s infinite' }} />
      <div className="gradient-orb orb-2" style={{ animation: 'orbFloat 10s infinite reverse' }} />

      <div className="login-card glass fade-in">
        {/* Siri Orb */}
        <div className="siri-orb-container">
          <div className="siri-orb">
            <div className="siri-orb-inner" />
          </div>
        </div>

        <h1 className="login-title">Aisha</h1>
        <p className="login-subtitle">Trợ lý AI điều khiển nhà thông minh</p>

        <div className="login-form">
          <div className="input-group">
            <label htmlFor="login-username">Username</label>
            <input
              id="login-username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              autoComplete="username"
            />
          </div>
          <div className="input-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              autoComplete="current-password"
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" onClick={handleLogin} disabled={loading}>
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>

          {/* ── Divider ─────────────────────────── */}
          <div className="login-divider">
            <span className="login-divider__line" />
            <span className="login-divider__text">hoặc</span>
            <span className="login-divider__line" />
          </div>

          {/* ── Google Sign-In (native GIS) ────── */}
          <div className="google-login-wrapper" ref={googleBtnRef} />
        </div>
      </div>
    </div>
  )
}
