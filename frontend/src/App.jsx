import { useEffect, useState } from 'react'
import useStore from './store/useStore'
import { getMe } from './api/client'
import { ToastProvider } from './ui'
import AppShell from './layouts/AppShell'
import AuthShell from './layouts/AuthShell'
import LoginPage from './features/auth/LoginPage'
import ChatPage from './features/chat/ChatPage'
import DevicesPage from './features/devices/DevicesPage'
import HistoryPage from './features/history/HistoryPage'
import AccountPage from './features/account/AccountPage'

export default function App() {
  return (
    <ToastProvider position="top-center">
      <AppRouter />
    </ToastProvider>
  )
}

function AppRouter() {
  const token = useStore(s => s.token)
  const user = useStore(s => s.user)
  const roles = useStore(s => s.roles)
  const activePage = useStore(s => s.activePage)
  const clearAuth = useStore(s => s.clearAuth)
  const setAuth = useStore(s => s.setAuth)
  const [loading, setLoading] = useState(true)

  // Restore session on mount
  useEffect(() => {
    if (token && !user) {
      getMe()
        .then(me => setAuth(me, token))
        .catch(() => clearAuth())
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) {
    return (
      <AuthShell>
        <BootSplash />
      </AuthShell>
    )
  }

  if (!token) {
    return (
      <AuthShell>
        <LoginPage />
      </AuthShell>
    )
  }

  // Guest không xem History → đổi về Chat
  const isGuest = roles.includes('guest')
  const currentPage = (isGuest && activePage === 'history') ? 'chat' : activePage

  return (
    <AppShell>
      {currentPage === 'chat'    && <ChatPage />}
      {currentPage === 'devices' && <DevicesPage />}
      {currentPage === 'history' && <HistoryPage />}
      {currentPage === 'account' && <AccountPage />}
    </AppShell>
  )
}

