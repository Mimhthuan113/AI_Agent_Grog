import { useState } from 'react'
import { login as apiLogin } from '../api/client'
import useStore from '../store/useStore'
import './LoginPage.css'

export default function LoginPage() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('changeme_strong_password_here')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setAuth = useStore(s => s.setAuth)

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
            <label>Username</label>
            <input
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              autoComplete="username"
            />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input
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
        </div>
      </div>
    </div>
  )
}
