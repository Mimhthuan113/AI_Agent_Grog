import useStore from '../store/useStore'
import { Pill } from '../ui'
import { formatDisplayName } from '../lib/format'
import './AppShell.css'

/**
 * AppShell — layout chính sau khi đăng nhập.
 * Header glass + main scroll + bottom nav.
 *
 * @param {React.ReactNode} children - Page content (Chat/Devices/History/Account)
 */
export default function AppShell({ children }) {
  const activePage = useStore(s => s.activePage)
  const setPage = useStore(s => s.setPage)
  const clearAuth = useStore(s => s.clearAuth)
  const user = useStore(s => s.user)
  const roles = useStore(s => s.roles)
  const displayName = useStore(s => s.displayName)
  const picture = useStore(s => s.picture)

  const isOwner = roles.includes('owner')
  const { theme, cyceTheme } = useTheme()

  return (
    <div className="app-shell">
      {/* Aurora background — DNA của Aisha */}
      <div className="aurora-canvas" aria-hidden>
        <div className="aurora-dot-3" />
      </div>

      {/* ── Header ───────────────────────── */}
      <header className="app-shell__header glass-surface">
        <button
          className="app-shell__brand"
          onClick={() => setPage('chat')}
          aria-label="Về trang chính"
        >
          <span className="app-shell__orb-mini" aria-hidden />
          <span className="app-shell__brand-text aurora-text">Aisha</span>
        </button>

        <div className="app-shell__actions">
          <button
            className="app-shell__user-pill"
            onClick={() => setPage('account')}
            aria-label="Mở trang tài khoản"
          >
            {picture ? (
              <img
                src={picture}
                alt=""
                className="app-shell__avatar"
                referrerPolicy="no-referrer"
              />
            ) : (
              <span className="app-shell__avatar-fallback" aria-hidden>
                {(displayName || user?.user_id || '?').charAt(0).toUpperCase()}
              </span>
            )}
            <span className="app-shell__user-name">
              {formatDisplayName(displayName || user?.user_id)}
            </span>
            <Pill tone={isOwner ? 'owner' : 'guest'} size="sm">
              {isOwner ? 'Chủ' : 'Khách'}
            </Pill>
          </button>

          <button
            className="app-shell__icon-btn"
            onClick={toggleTheme}
            title={`Chế độ ${theme === 'light' ? 'Sáng' : 'Tối'} — bấm để đổi`}
            aria-label="Đổi chủ đề sáng / tối"
          >
            {theme === 'light' ? <SunIcon /> : <MoonIcon />}
          </button>

          <button
            className="app-shell__icon-btn app-shell__icon-btn--logout"
            onClick={clearAuth}
            title="Đăng xuất"
            aria-label="Đăng xuất"
          >
            <PowerIcon />
          </button>
        </div>
      </header>

      {/* ── Main (page transition wrapper) ─ */}
      <main className="app-shell__main">
        <div key={activePage} className="app-shell__page">
          {children}
        </div>
      </main>

      {/* ── Bottom Navigation ───────────── */}
      <nav className="app-shell__nav glass-surface" role="tablist" aria-label="Điều hướng">
        <NavTab
          icon={<ChatIcon />}
          label="Trò chuyện"
          active={activePage === 'chat'}
          onClick={() => setPage('chat')}
        />
        <NavTab
          icon={<DevicesIcon />}
          label="Thiết bị"
          active={activePage === 'devices'}
          onClick={() => setPage('devices')}
        />
        {isOwner && (
          <NavTab
            icon={<HistoryIcon />}
            label="Lịch sử"
            active={activePage === 'history'}
            onClick={() => setPage('history')}
          />
        )}
        <NavTab
          icon={<UserIcon />}
          label="Tài khoản"
          active={activePage === 'account'}
          onClick={() => setPage('account')}
        />
      </nav>
    </div>
  )
}

function NavTab({ icon, label, active, onClick }) {
  return (
    <button
      className={`nav-tab ${active ? 'is-active' : ''}`}
      onClick={onClick}
      role="tab"
      aria-selected={active}
    >
      <span className="nav-tab__icon">{icon}</span>
      <span className="nav-tab__label">{label}</span>
      {active && <span className="nav-tab__indicator" aria-hidden />}
    </button>
  )
}

/* ── Inline SVG icons (no external lib, APK-friendly) ─── */
function ChatIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  )
}
function DevicesIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5"/>
      <rect x="14" y="3" width="7" height="7" rx="1.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5"/>
      <rect x="14" y="14" width="7" height="7" rx="1.5"/>
    </svg>
  )
}
function HistoryIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
      <path d="M3 3v5h5"/>
      <path d="M12 7v5l3 2"/>
    </svg>
  )
}
function UserIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/>
      <path d="M4 21a8 8 0 0 1 16 0"/>
    </svg>
  )
}
function PowerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
      <line x1="12" y1="2" x2="12" y2="12"/>
    </svg>
  )
}
function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
    </svg>
  )
}
function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  )
}
