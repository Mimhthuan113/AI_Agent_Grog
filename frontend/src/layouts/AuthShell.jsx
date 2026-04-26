import './AuthShell.css'

/**
 * AuthShell — fullscreen aurora background cho các trang auth (Login, Register).
 */
export default function AuthShell({ children }) {
  return (
    <div className="auth-shell">
      <div className="aurora-canvas" aria-hidden>
        <div className="aurora-dot-3" />
      </div>
      <main className="auth-shell__main">
        {children}
      </main>
    </div>
  )
}
