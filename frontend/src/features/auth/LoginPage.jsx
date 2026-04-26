import { useState, useEffect, useRef } from 'react'
import { login as apiLogin, googleLogin as apiGoogleLogin, getMe } from '../../api/client'
import useStore from '../../store/useStore'
import { Button, Input, Card, useToast } from '../../ui'
import './LoginPage.css'

const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  '1024198635802-ke42fatp2odl6coh5ploporrd62qcnve.apps.googleusercontent.com'

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
  const toast = useToast()

  useEffect(() => {
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

  const handleLogin = async (e) => {
    e?.preventDefault?.()
    setError('')
    setLoading(true)
    try {
      const data = await apiLogin(username, password)
      setAuth({ user_id: data.user_id }, data.access_token)
      toast.success('Đăng nhập thành công')
    } catch (e) {
      const msg = e.response?.data?.detail || 'Không kết nối được server'
      setError(msg)
    }
    setLoading(false)
  }

  const handleGoogleCallback = async (response) => {
    setError('')
    setLoading(true)
    try {
      const data = await apiGoogleLogin(response.credential)
      const me = await getMe()
      setAuth(me, data.access_token)
      toast.success(`Chào mừng ${me.user_id?.split('@')[0] || 'bạn'}`)
    } catch (e) {
      const msg = e.response?.data?.detail || 'Đăng nhập Google thất bại'
      setError(msg)
    }
    setLoading(false)
  }

  return (
    <div className="login fade-in-up">
      <Card variant="aurora" className="login__card">
        {/* Aisha orb signature */}
        <div className="login__orb-wrap" aria-hidden>
          <div className="login__orb">
            <div className="login__orb-inner" />
          </div>
        </div>

        <h1 className="login__title aurora-text">Aisha</h1>
        <p className="login__subtitle">
          Trợ lý AI điều khiển nhà thông minh
        </p>

        <form className="login__form" onSubmit={handleLogin}>
          <Input
            label="Tên đăng nhập"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            iconLeft={<UserIcon />}
            size="lg"
          />
          <Input
            label="Mật khẩu"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            iconLeft={<LockIcon />}
            size="lg"
            error={error}
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={loading}
            iconRight={!loading && <ArrowRight />}
          >
            {loading ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </Button>

          <div className="login__divider">
            <span className="login__divider-line" />
            <span className="login__divider-text">hoặc</span>
            <span className="login__divider-line" />
          </div>

          <div className="login__google" ref={googleBtnRef} />
        </form>
      </Card>

      <p className="login__hint">
        Lần đầu sử dụng? Liên hệ chủ nhà để được cấp tài khoản.
      </p>
    </div>
  )
}

function UserIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/>
      <path d="M4 21a8 8 0 0 1 16 0"/>
    </svg>
  )
}
function LockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="11" width="16" height="10" rx="2"/>
      <path d="M8 11V7a4 4 0 0 1 8 0v4"/>
    </svg>
  )
}
function ArrowRight() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12"/>
      <polyline points="12 5 19 12 12 19"/>
    </svg>
  )
}
