import { useState, useEffect } from 'react'
import useStore from './store/useStore'
import { getMe } from './api/client'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DevicesPage from './pages/DevicesPage'
import HistoryPage from './pages/HistoryPage'
import AccountPage from './pages/AccountPage'
import './App.css'

export default function App() {
  const token = useStore(s => s.token)
  const activePage = useStore(s => s.activePage)
  const setPage = useStore(s => s.setPage)
  const clearAuth = useStore(s => s.clearAuth)
  const user = useStore(s => s.user)
  const roles = useStore(s => s.roles)
  const setAuth = useStore(s => s.setAuth)
  const displayName = useStore(s => s.displayName)
  const picture = useStore(s => s.picture)
  const [loading, setLoading] = useState(true)

  const isOwner = roles.includes('owner')
  const isGuest = roles.includes('guest')

  // Restore session on mount
  useEffect(() => {
    if (token && !user) {
      getMe()
        .then(me => {
          setAuth(me, token)
        })
        .catch(() => {
          clearAuth()
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  if (loading) {
    return (
      <div className="app-loading">
        <div className="siri-mini-orb loading-orb" />
        <p>Đang khởi tạo Aisha...</p>
      </div>
    )
  }

  if (!token) return <LoginPage />

  // Guest chỉ được xem Chat + Devices, không được xem History
  const guestForceChat = isGuest && activePage === 'history'
  const currentPage = guestForceChat ? 'chat' : activePage

  return (
    <div className="app-layout">
      {/* Background orbs */}
      <div className="gradient-orb orb-1" />
      <div className="gradient-orb orb-2" />

      {/* Header */}
      <header className="app-header glass">
        <div className="header-left">
          <div className="siri-mini-orb" />
          <h1>Aisha</h1>
        </div>
        <div className="header-right">
          <span className="user-pill" onClick={() => setPage('account')} style={{ cursor: 'pointer' }}>
            {picture ? (
              <img src={picture} alt="" className="user-avatar" referrerPolicy="no-referrer" />
            ) : (
              <span className="dot-online" />
            )}
            {formatDisplayName(displayName || user?.user_id)}
            <span className={`role-badge ${isOwner ? 'role-owner' : 'role-guest'}`}>
              {isOwner ? '👑 Owner' : '👤 Guest'}
            </span>
          </span>
          <button className="btn-logout" onClick={() => { clearAuth() }} title="Đăng xuất">
            ⏻
          </button>
        </div>
      </header>

      {/* Pages */}
      <main className="app-main">
        {currentPage === 'chat' && <ChatPage />}
        {currentPage === 'devices' && <DevicesPage />}
        {currentPage === 'history' && <HistoryPage />}
        {currentPage === 'account' && <AccountPage />}
      </main>

      {/* Bottom Navigation */}
      <nav className="bottom-bar glass">
        <NavBtn icon="💬" label="Chat" active={currentPage === 'chat'}
          onClick={() => setPage('chat')} />
        <NavBtn icon="📱" label="Thiết bị" active={currentPage === 'devices'}
          onClick={() => setPage('devices')} />
        {isOwner && (
          <NavBtn icon="📋" label="Lịch sử" active={currentPage === 'history'}
            onClick={() => setPage('history')} />
        )}
        <NavBtn icon="👤" label="Tài khoản" active={currentPage === 'account'}
          onClick={() => setPage('account')} />
      </nav>
    </div>
  )
}

function NavBtn({ icon, label, active, onClick }) {
  return (
    <button className={`nav-btn ${active ? 'active' : ''}`} onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      <span className="nav-label">{label}</span>
      {active && <span className="nav-indicator" />}
    </button>
  )
}

/**
 * Rút gọn tên hiển thị:
 * - Nếu là email → lấy phần trước @ và capitalize
 * - Nếu là tên bình thường → giữ nguyên
 */
function formatDisplayName(raw) {
  if (!raw) return 'User'
  if (raw.includes('@')) {
    const name = raw.split('@')[0]
    return name.charAt(0).toUpperCase() + name.slice(1)
  }
  return raw
}
