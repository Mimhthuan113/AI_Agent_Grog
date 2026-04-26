import { useState, useEffect } from 'react'
import { listUsers, createUser, deleteUser, updateUser } from '../api/client'
import { getApiUrl, setApiUrl, hasUserApiOverride, isCapacitorNative, pingApiUrl } from '../api/config'
import useStore from '../store/useStore'
import './AccountPage.css'

export default function AccountPage() {
  const user = useStore(s => s.user)
  const roles = useStore(s => s.roles)
  const displayName = useStore(s => s.displayName)
  const picture = useStore(s => s.picture)
  const clearAuth = useStore(s => s.clearAuth)

  const isOwner = roles.includes('owner')
  const isGoogle = user?.user_id?.includes('@')

  return (
    <div className="acct">
      <div className="acct__glow acct__glow--1" />
      <div className="acct__glow acct__glow--2" />

      <div className="acct__container">
        {/* ══ Profile Hero ══ */}
        <section className="acct__hero">
          <div className="acct__avatar-ring">
            {picture ? (
              <img src={picture} alt="" className="acct__avatar-img" referrerPolicy="no-referrer" />
            ) : (
              <div className="acct__avatar-fallback">
                {fmt(displayName || user?.user_id)[0].toUpperCase()}
              </div>
            )}
            <span className="acct__online-dot" />
          </div>
          <h2 className="acct__name">{fmt(displayName || user?.user_id)}</h2>
          <div className="acct__badges">
            <span className={`acct__badge acct__badge--${isOwner ? 'owner' : 'guest'}`}>
              {isOwner ? '👑 Chủ nhà' : '👤 Khách'}
            </span>
            {isGoogle && <span className="acct__badge acct__badge--google"><GIcon /> Google</span>}
          </div>
        </section>

        {/* ══ Info + Permissions (Accordion) ══ */}
        <Accordion icon="👤" title="Thông tin tài khoản" defaultOpen>
          <InfoRow label="User ID" value={user?.user_id || '—'} />
          <InfoRow label="Phương thức" value={isGoogle ? 'Google OAuth2' : 'Nội bộ'} />
          <InfoRow label="Phiên" value={user?.session_id || '—'} mono />
        </Accordion>

        <Accordion icon="🛡️" title="Quyền hạn">
          <PermList isOwner={isOwner} />
        </Accordion>

        {/* ══ User Management — Owner Only ══ */}
        {isOwner && (
          <Accordion icon="👥" title="Quản lý tài khoản" defaultOpen>
            <UserManagement />
          </Accordion>
        )}

        {/* ══ Backend URL — chủ yếu phục vụ APK Android ══ */}
        <Accordion icon="🔌" title="Cấu hình kết nối Backend" defaultOpen={isCapacitorNative()}>
          <BackendUrlSettings />
        </Accordion>

        <button className="acct__logout" onClick={clearAuth}>
          <span>⏻</span> Đăng xuất
        </button>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════
   Backend URL Settings — runtime override
   Cho phép user (đặc biệt khi chạy APK Android) trỏ frontend
   tới IP LAN của máy chạy backend, không cần build lại.
   ═══════════════════════════════════════ */
function BackendUrlSettings() {
  const currentUrl = getApiUrl()
  const [url, setUrl] = useState(currentUrl)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)  // null | 'ok' | 'fail'
  const [saved, setSaved] = useState(false)
  const isOverride = hasUserApiOverride()
  const isNative = isCapacitorNative()

  const handleSave = () => {
    try {
      setApiUrl(url)
      setSaved(true)
      setTestResult(null)
      setTimeout(() => setSaved(false), 1800)
    } catch (e) {
      alert(e.message || 'URL không hợp lệ')
    }
  }

  const handleReset = () => {
    setApiUrl('')
    setUrl(getApiUrl())
    setSaved(true)
    setTestResult(null)
    setTimeout(() => setSaved(false), 1800)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    const ok = await pingApiUrl(url)
    setTestResult(ok ? 'ok' : 'fail')
    setTesting(false)
  }

  return (
    <div className="bcfg">
      <p className="bcfg__hint">
        URL hiện tại: <code className="bcfg__code">{currentUrl}</code>
        {isOverride && <span className="bcfg__tag">đã override</span>}
      </p>
      {isNative && (
        <p className="bcfg__warn">
          📱 App đang chạy trong APK — <b>localhost không trỏ về máy của bạn</b>.
          Hãy dùng IP LAN, ví dụ <code>http://192.168.1.10:8000</code>.
        </p>
      )}
      <input
        type="text"
        className="bcfg__input"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://192.168.1.10:8000"
        spellCheck={false}
        autoComplete="off"
      />
      <div className="bcfg__row">
        <button className="bcfg__btn bcfg__btn--test" onClick={handleTest} disabled={testing || !url}>
          {testing ? '⏳ Đang test…' : '🔍 Test kết nối'}
        </button>
        <button className="bcfg__btn bcfg__btn--save" onClick={handleSave} disabled={!url || url === currentUrl}>
          💾 Lưu
        </button>
        {isOverride && (
          <button className="bcfg__btn bcfg__btn--reset" onClick={handleReset}>
            ↺ Reset
          </button>
        )}
      </div>
      {testResult === 'ok' && <p className="bcfg__msg bcfg__msg--ok">✅ Backend phản hồi</p>}
      {testResult === 'fail' && <p className="bcfg__msg bcfg__msg--fail">❌ Không kết nối được — kiểm tra IP, port, firewall</p>}
      {saved && <p className="bcfg__msg bcfg__msg--ok">💾 Đã lưu, các request sẽ dùng URL mới ngay</p>}
    </div>
  )
}

/* ═══════════════════════════════════════
   Accordion — Collapsible Section
   ═══════════════════════════════════════ */
function Accordion({ icon, title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={`acc ${open ? 'acc--open' : ''}`}>
      <button className="acc__header" onClick={() => setOpen(!open)}>
        <span className="acc__icon">{icon}</span>
        <span className="acc__title">{title}</span>
        <span className={`acc__arrow ${open ? 'acc__arrow--up' : ''}`}>▾</span>
      </button>
      <div className="acc__body" style={{ display: open ? 'block' : 'none' }}>
        {children}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════
   Permissions List
   ═══════════════════════════════════════ */
function PermList({ isOwner }) {
  const perms = isOwner
    ? ['🏠 Điều khiển toàn bộ thiết bị', '📱 Mở ứng dụng', '📋 Xem lịch sử', '⚙️ Cấu hình hệ thống', '👥 Quản lý tài khoản']
    : ['💬 Chat với Aisha', '🏠 Điều khiển cơ bản']
  const denied = isOwner
    ? []
    : ['📱 Mở ứng dụng', '📋 Xem lịch sử', '⚙️ Cấu hình']

  return (
    <div className="perm-list">
      {perms.map((p, i) => <div key={i} className="perm perm--on"><span>{p}</span><span className="perm__ok">✓</span></div>)}
      {denied.map((p, i) => <div key={i} className="perm perm--off"><span>{p}</span><span className="perm__no">✕</span></div>)}
    </div>
  )
}

/* ═══════════════════════════════════════
   User Management (CRUD)
   ═══════════════════════════════════════ */
function UserManagement() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // { type: 'add'|'edit'|'delete', data }

  const load = async () => {
    setLoading(true)
    try { const d = await listUsers(); setUsers(d.users || []) }
    catch { setUsers([]) }
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  // ── Actions ──
  const handleAdd = async (form) => {
    await createUser(form.username, form.password, form.display_name || form.username, form.role)
    setModal(null)
    await load()
  }

  const handleEdit = async (username, updates) => {
    await updateUser(username, updates)
    setModal(null)
    await load()
  }

  const handleDelete = async (username) => {
    await deleteUser(username)
    setModal(null)
    await load()
  }

  const editable = (u) => u.auth_method === 'local' && u.created_at !== '—'

  return (
    <div className="um">
      {/* Add Button */}
      <button className="um__add" onClick={() => setModal({ type: 'add' })}>
        ＋ Thêm tài khoản
      </button>

      {/* User List */}
      {loading ? (
        <div className="um__loading">Đang tải...</div>
      ) : (
        <div className="um__list">
          {users.map((u, i) => (
            <div key={i} className="um__row">
              <div className="um__av">{(u.display_name || u.username)[0].toUpperCase()}</div>
              <div className="um__info">
                <span className="um__name">{u.display_name || u.username}</span>
                <span className="um__meta">@{u.username} · {u.auth_method}</span>
              </div>
              <span className={`um__role um__role--${u.role}`}>
                {u.role === 'owner' ? '👑' : '👤'}
              </span>
              {editable(u) && (
                <div className="um__actions">
                  <button className="um__btn um__btn--edit" title="Sửa"
                    onClick={() => setModal({ type: 'edit', data: u })}>✏️</button>
                  <button className="um__btn um__btn--del" title="Xoá"
                    onClick={() => setModal({ type: 'delete', data: u })}>🗑️</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Modals ── */}
      {modal?.type === 'add' && (
        <UserFormModal
          title="Thêm tài khoản mới"
          onClose={() => setModal(null)}
          onSubmit={handleAdd}
        />
      )}
      {modal?.type === 'edit' && (
        <UserFormModal
          title={`Sửa: ${modal.data.display_name}`}
          initial={modal.data}
          onClose={() => setModal(null)}
          onSubmit={(form) => handleEdit(modal.data.username, form)}
        />
      )}
      {modal?.type === 'delete' && (
        <ConfirmModal
          title="Xoá tài khoản"
          message={`Bạn chắc chắn muốn xoá "${modal.data.display_name || modal.data.username}"? Hành động này không thể hoàn tác.`}
          confirmLabel="🗑️ Xoá"
          danger
          onClose={() => setModal(null)}
          onConfirm={() => handleDelete(modal.data.username)}
        />
      )}
    </div>
  )
}

/* ═══════════════════════════════════════
   User Form Modal (Add / Edit)
   ═══════════════════════════════════════ */
function UserFormModal({ title, initial, onClose, onSubmit }) {
  const isEdit = !!initial
  const [form, setForm] = useState({
    username: initial?.username || '',
    password: '',
    display_name: initial?.display_name || '',
    role: initial?.role || 'guest',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!isEdit && (!form.username || !form.password)) {
      setError('Username và mật khẩu bắt buộc')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      if (isEdit) {
        const updates = {}
        if (form.display_name !== initial.display_name) updates.display_name = form.display_name
        if (form.role !== initial.role) updates.role = form.role
        if (form.password) updates.password = form.password
        await onSubmit(updates)
      } else {
        await onSubmit(form)
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Lỗi, vui lòng thử lại')
    }
    setSubmitting(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">{title}</h3>
          <button className="modal__close" onClick={onClose}>✕</button>
        </div>
        <div className="modal__body">
          {!isEdit && (
            <div className="modal__field">
              <label>Tên đăng nhập *</label>
              <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
                placeholder="vd: nguoinha2" autoFocus />
            </div>
          )}
          <div className="modal__field">
            <label>{isEdit ? 'Mật khẩu mới (bỏ trống = giữ nguyên)' : 'Mật khẩu *'}</label>
            <input type="password" value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              placeholder={isEdit ? '••••••••' : 'Tối thiểu 4 ký tự'} />
          </div>
          <div className="modal__field">
            <label>Tên hiển thị</label>
            <input value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })}
              placeholder="vd: Nguyễn Văn A" />
          </div>
          <div className="modal__field">
            <label>Vai trò</label>
            <div className="modal__roles">
              <button className={`modal__role-btn ${form.role === 'guest' ? 'active' : ''}`}
                onClick={() => setForm({ ...form, role: 'guest' })}>
                👤 Khách
              </button>
              <button className={`modal__role-btn ${form.role === 'owner' ? 'active' : ''}`}
                onClick={() => setForm({ ...form, role: 'owner' })}>
                👑 Chủ nhà
              </button>
            </div>
          </div>
          {error && <div className="modal__error">{error}</div>}
        </div>
        <div className="modal__footer">
          <button className="modal__btn modal__btn--cancel" onClick={onClose}>Huỷ</button>
          <button className="modal__btn modal__btn--submit" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Đang xử lý...' : isEdit ? '💾 Lưu' : '✓ Tạo'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════
   Confirm Modal (Delete)
   ═══════════════════════════════════════ */
function ConfirmModal({ title, message, confirmLabel, danger, onClose, onConfirm }) {
  const [loading, setLoading] = useState(false)

  const handle = async () => {
    setLoading(true)
    try { await onConfirm() }
    catch (e) { alert(e.response?.data?.detail || 'Lỗi') }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--sm" onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">{title}</h3>
          <button className="modal__close" onClick={onClose}>✕</button>
        </div>
        <div className="modal__body">
          <p className="modal__msg">{message}</p>
        </div>
        <div className="modal__footer">
          <button className="modal__btn modal__btn--cancel" onClick={onClose}>Huỷ bỏ</button>
          <button className={`modal__btn ${danger ? 'modal__btn--danger' : 'modal__btn--submit'}`}
            onClick={handle} disabled={loading}>
            {loading ? 'Đang xoá...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Helpers ──────────────────────────── */
function InfoRow({ label, value, mono }) {
  return (
    <div className="acct__info-row">
      <span className="acct__info-label">{label}</span>
      <span className={`acct__info-value ${mono ? 'acct__info-value--mono' : ''}`}>{value}</span>
    </div>
  )
}

function fmt(raw) {
  if (!raw) return 'User'
  if (raw.includes('@')) return raw.split('@')[0].charAt(0).toUpperCase() + raw.split('@')[0].slice(1)
  return raw
}

function GIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" style={{ flexShrink: 0 }}>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  )
}
