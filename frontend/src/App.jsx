import { useState } from 'react'
import useStore from './store/useStore'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DevicesPage from './pages/DevicesPage'
import HistoryPage from './pages/HistoryPage'
import './App.css'

export default function App() {
  const token = useStore(s => s.token)
  const activePage = useStore(s => s.activePage)
  const setPage = useStore(s => s.setPage)
  const clearAuth = useStore(s => s.clearAuth)
  const user = useStore(s => s.user)

  if (!token) return <LoginPage />

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
          <span className="user-pill">
            <span className="dot-online" />
            {user?.user_id || 'admin'}
          </span>
          <button className="btn-logout" onClick={() => { clearAuth() }}>
            ⏻
          </button>
        </div>
      </header>

      {/* Pages */}
      <main className="app-main">
        {activePage === 'chat' && <ChatPage />}
        {activePage === 'devices' && <DevicesPage />}
        {activePage === 'history' && <HistoryPage />}
      </main>

      {/* Bottom Navigation */}
      <nav className="bottom-bar glass">
        <NavBtn icon="💬" label="Chat" active={activePage === 'chat'} onClick={() => setPage('chat')} />
        <NavBtn icon="📱" label="Thiết bị" active={activePage === 'devices'} onClick={() => setPage('devices')} />
        <NavBtn icon="📋" label="Lịch sử" active={activePage === 'history'} onClick={() => setPage('history')} />
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
