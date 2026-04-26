import { useState, useEffect, useCallback } from 'react'
import { listUsers, createUser, deleteUser, updateUser } from '../../api/client'
import { getApiUrl, setApiUrl, hasUserApiOverride, isCapacitorNative, pingApiUrl } from '../../api/config'
import useStore from '../../store/useStore'
import { Button, Input, Card, Pill, EmptyState, useToast } from '../../ui'
import { formatDisplayName } from '../../lib/format'
import './AccountPage.css'

export default function AccountPage() {
  const user = useStore(s => s.user)
  const roles = useStore(s => s.roles)
  const displayName = useStore(s => s.displayName)
  const picture = useStore(s => s.picture)
  const clearAuth = useStore(s => s.clearAuth)

  const isOwner = roles.includes('owner')
  const isGoogle = user?.user_id?.includes('@')
  const name = formatDisplayName(displayName || user?.user_id)

  return (
    <div className="acct fade-in-up">
      <div className="acct__container">

        {/* ══ Hero ════════════════════════ */}
        <section className="acct__hero">
          <div className="acct__avatar-ring">
            {picture ? (
              <img src={picture} alt="" className="acct__avatar-img" referrerPolicy="no-referrer" />
            ) : (
              <div className="acct__avatar-fallback">{name[0]?.toUpperCase()}</div>
            )}
            <span className="acct__online-dot" aria-hidden />
          </div>
          <h2 className="acct__name">{name}</h2>
          <div className="acct__badges">
            <Pill tone={isOwner ? 'owner' : 'guest'} icon={isOwner ? '👑' : '👤'}>
              {isOwner ? 'Chủ nhà' : 'Khách'}
            </Pill>
            {isGoogle && (
              <Pill tone="info" icon={<GIcon />}>Google</Pill>
            )}
          </div>
        </section>

        {/* ══ Sections ════════════════════ */}
        <Section icon={<UserIcon />} title="Thông tin tài khoản" defaultOpen>
          <InfoRow label="User ID" value={user?.user_id || '—'} mono />
          <InfoRow label="Phương thức" value={isGoogle ? 'Google OAuth2' : 'Nội bộ'} />
          <InfoRow label="Phiên" value={user?.session_id || '—'} mono />
        </Section>

        <Section icon={<ShieldIcon />} title="Quyền hạn">
          <PermList isOwner={isOwner} />
        </Section>

        {isOwner && (
          <Section icon={<UsersIcon />} title="Quản lý tài khoản" defaultOpen>
            <UserManagement />
          </Section>
        )}

        <Section icon={<PlugIcon />} title="Cấu hình kết nối Backend" defaultOpen={isCapacitorNative()}>
          <BackendUrlSettings />
        </Section>

        <Button
          variant="danger"
          size="lg"
          fullWidth
          onClick={clearAuth}
          iconLeft={<PowerIcon />}
          className="acct__logout"
        >
          Đăng xuất
        </Button>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════
   Section — Collapsible group with header
   ═══════════════════════════════════════ */
function Section({ icon, title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Card variant="flat" padded={false} className={`acct-sec ${open ? 'is-open' : ''}`}>
      <button
        className="acct-sec__head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="acct-sec__icon">{icon}</span>
        <span className="acct-sec__title">{title}</span>
        <span className={`acct-sec__chevron ${open ? 'is-up' : ''}`} aria-hidden>
          <ChevronIcon />
        </span>
      </button>
      {open && <div className="acct-sec__body">{children}</div>}
    </Card>
  )
}

/* ═══════════════════════════════════════
   Permissions
   ═══════════════════════════════════════ */
function PermList({ isOwner }) {
  const granted = isOwner
    ? ['🏠 Điều khiển toàn bộ thiết bị', '📱 Mở ứng dụng', '📋 Xem lịch sử', '⚙️ Cấu hình hệ thống', '👥 Quản lý tài khoản']
    : ['💬 Chat với Aisha', '🏠 Điều khiển cơ bản']
  const denied = isOwner
    ? []
    : ['📱 Mở ứng dụng', '📋 Xem lịch sử', '⚙️ Cấu hình']

  return (
    <ul className="perm-list">
      {granted.map((p, i) => (
        <li key={`g${i}`} className="perm-list__row is-on">
          <span>{p}</span>
          <span className="perm-list__mark is-on" aria-label="Có quyền">✓</span>
        </li>
      ))}
      {denied.map((p, i) => (
        <li key={`d${i}`} className="perm-list__row is-off">
          <span>{p}</span>
          <span className="perm-list__mark is-off" aria-label="Không có quyền">✕</span>
        </li>
      ))}
    </ul>
  )
}

/* ═══════════════════════════════════════
   Backend URL Settings
   ═══════════════════════════════════════ */
function BackendUrlSettings() {
  const currentUrl = getApiUrl()
  const [url, setUrl] = useState(currentUrl)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const isOverride = hasUserApiOverride()
  const isNative = isCapacitorNative()
  const toast = useToast()

  const handleSave = () => {
    try {
      setApiUrl(url)
      setTestResult(null)
      toast.success('Đã lưu — request mới sẽ dùng URL này ngay')
    } catch (e) {
      toast.error(e.message || 'URL không hợp lệ')
    }
  }

  const handleReset = () => {
    setApiUrl('')
    setUrl(getApiUrl())
    setTestResult(null)
    toast.info('Đã reset về URL mặc định')
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    const ok = await pingApiUrl(url)
    setTestResult(ok ? 'ok' : 'fail')
    setTesting(false)
    if (ok) toast.success('Backend phản hồi tốt')
    else toast.error('Không kết nối được — kiểm tra IP, port, firewall')
  }

  return (
    <div className="bcfg">
      <div className="bcfg__current">
        <span className="bcfg__label">URL hiện tại</span>
        <code className="bcfg__code">{currentUrl}</code>
        {isOverride && <Pill tone="info" size="sm">đã override</Pill>}
      </div>

      {isNative && (
        <Card variant="flat" className="bcfg__warn">
          <p>
            <strong>📱 App đang chạy trong APK</strong> — <code>localhost</code> không trỏ về máy của bạn.
            Hãy dùng IP LAN, ví dụ <code>http://192.168.1.10:8000</code>.
          </p>
        </Card>
      )}

      <Input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://192.168.1.10:8000"
        spellCheck={false}
        autoComplete="off"
        size="lg"
      />

      <div className="bcfg__actions">
        <Button
          variant="secondary"
          onClick={handleTest}
          disabled={!url}
          loading={testing}
          iconLeft={!testing && <SearchIcon />}
        >
          {testing ? 'Đang test…' : 'Test kết nối'}
        </Button>
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!url || url === currentUrl}
        >
          Lưu
        </Button>
        {isOverride && (
          <Button variant="ghost" onClick={handleReset}>
            Reset
          </Button>
        )}
      </div>

      {testResult === 'ok' && (
        <p className="bcfg__msg is-ok">✓ Backend phản hồi</p>
      )}
      {testResult === 'fail' && (
        <p className="bcfg__msg is-fail">✕ Không kết nối được</p>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════
   User Management (CRUD)
   ═══════════════════════════════════════ */
function UserManagement() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await listUsers()
      setUsers(d.users || [])
    } catch {
      setUsers([])
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const handleAdd = async (form) => {
    await createUser(form.username, form.password, form.display_name || form.username, form.role)
    setModal(null)
    await load()
    toast.success(`Đã tạo tài khoản ${form.username}`)
  }

  const handleEdit = async (username, updates) => {
    await updateUser(username, updates)
    setModal(null)
    await load()
    toast.success(`Đã cập nhật ${username}`)
  }

  const handleDelete = async (username) => {
    await deleteUser(username)
    setModal(null)
    await load()
    toast.success(`Đã xoá ${username}`)
  }

  const editable = (u) => u.auth_method === 'local' && u.created_at !== '—'

  return (
    <div className="um">
      <Button
        variant="secondary"
        fullWidth
        onClick={() => setModal({ type: 'add' })}
        iconLeft={<PlusIcon />}
      >
        Thêm tài khoản
      </Button>

      {loading ? (
        <div className="um__skeleton">
          {[0,1,2].map((i) => <div key={i} className="um__skeleton-row" aria-hidden />)}
        </div>
      ) : users.length === 0 ? (
        <EmptyState size="sm" title="Chưa có tài khoản nào" />
      ) : (
        <ul className="um__list">
          {users.map((u, i) => (
            <li key={i} className="um__row">
              <div className="um__avatar">
                {(u.display_name || u.username)[0].toUpperCase()}
              </div>
              <div className="um__info">
                <span className="um__name">{u.display_name || u.username}</span>
                <span className="um__meta">@{u.username} · {u.auth_method}</span>
              </div>
              <Pill tone={u.role === 'owner' ? 'owner' : 'guest'} size="sm">
                {u.role === 'owner' ? '👑 Chủ' : '👤 Khách'}
              </Pill>
              {editable(u) && (
                <div className="um__actions">
                  <button
                    className="um__icon-btn"
                    onClick={() => setModal({ type: 'edit', data: u })}
                    aria-label="Sửa"
                    title="Sửa"
                  >
                    <PencilIcon />
                  </button>
                  <button
                    className="um__icon-btn um__icon-btn--danger"
                    onClick={() => setModal({ type: 'delete', data: u })}
                    aria-label="Xoá"
                    title="Xoá"
                  >
                    <TrashIcon />
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {modal?.type === 'add' && (
        <UserFormModal
          title="Thêm tài khoản mới"
          onClose={() => setModal(null)}
          onSubmit={handleAdd}
        />
      )}
      {modal?.type === 'edit' && (
        <UserFormModal
          title={`Sửa: ${modal.data.display_name || modal.data.username}`}
          initial={modal.data}
          onClose={() => setModal(null)}
          onSubmit={(form) => handleEdit(modal.data.username, form)}
        />
      )}
      {modal?.type === 'delete' && (
        <ConfirmModal
          title="Xoá tài khoản"
          message={`Bạn chắc chắn muốn xoá "${modal.data.display_name || modal.data.username}"? Hành động này không thể hoàn tác.`}
          confirmLabel="Xoá"
          danger
          onClose={() => setModal(null)}
          onConfirm={() => handleDelete(modal.data.username)}
        />
      )}
    </div>
  )
}

/* ═══════════════════════════════════════
   User Form Modal
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

  const handleSubmit = async (e) => {
    e?.preventDefault?.()
    if (!isEdit && (!form.username || !form.password)) {
      setError('Username và mật khẩu là bắt buộc')
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
    <ModalOverlay onClose={onClose}>
      <Card variant="elevated" className="acct-modal" padded={false}>
        <div className="acct-modal__head">
          <h3 className="acct-modal__title">{title}</h3>
          <button className="acct-modal__close" onClick={onClose} aria-label="Đóng">×</button>
        </div>
        <form className="acct-modal__body" onSubmit={handleSubmit}>
          {!isEdit && (
            <Input
              label="Tên đăng nhập"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="vd: nguoinha2"
              autoFocus
            />
          )}
          <Input
            label={isEdit ? 'Mật khẩu mới (bỏ trống = giữ nguyên)' : 'Mật khẩu'}
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder={isEdit ? '••••••••' : 'Tối thiểu 4 ký tự'}
          />
          <Input
            label="Tên hiển thị"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            placeholder="vd: Nguyễn Văn A"
          />

          <div className="acct-modal__field">
            <label className="acct-modal__label">Vai trò</label>
            <div className="acct-modal__roles">
              <button
                type="button"
                className={`acct-modal__role ${form.role === 'guest' ? 'is-active' : ''}`}
                onClick={() => setForm({ ...form, role: 'guest' })}
              >
                👤 Khách
              </button>
              <button
                type="button"
                className={`acct-modal__role ${form.role === 'owner' ? 'is-active' : ''}`}
                onClick={() => setForm({ ...form, role: 'owner' })}
              >
                👑 Chủ nhà
              </button>
            </div>
          </div>

          {error && <p className="acct-modal__error">{error}</p>}

          <div className="acct-modal__foot">
            <Button type="button" variant="ghost" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              {isEdit ? 'Lưu' : 'Tạo'}
            </Button>
          </div>
        </form>
      </Card>
    </ModalOverlay>
  )
}

/* ═══════════════════════════════════════
   Confirm Modal (Delete)
   ═══════════════════════════════════════ */
function ConfirmModal({ title, message, confirmLabel, danger, onClose, onConfirm }) {
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  const handle = async () => {
    setLoading(true)
    try { await onConfirm() }
    catch (e) { toast.error(e.response?.data?.detail || 'Lỗi') }
    setLoading(false)
  }

  return (
    <ModalOverlay onClose={onClose}>
      <Card variant="elevated" className="acct-modal acct-modal--sm" padded={false}>
        <div className="acct-modal__head">
          <h3 className="acct-modal__title">{title}</h3>
          <button className="acct-modal__close" onClick={onClose} aria-label="Đóng">×</button>
        </div>
        <div className="acct-modal__body">
          <p className="acct-modal__msg">{message}</p>
          <div className="acct-modal__foot">
            <Button variant="ghost" onClick={onClose}>Huỷ bỏ</Button>
            <Button
              variant={danger ? 'danger' : 'primary'}
              onClick={handle}
              loading={loading}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </Card>
    </ModalOverlay>
  )
}

function ModalOverlay({ onClose, children }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="acct-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="acct-modal-overlay__inner" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════
   Helpers
   ═══════════════════════════════════════ */
function InfoRow({ label, value, mono }) {
  return (
    <div className="info-row">
      <span className="info-row__label">{label}</span>
      <span className={`info-row__value ${mono ? 'is-mono' : ''}`}>{value}</span>
    </div>
  )
}

/* ── Icons ─────────────────────────────── */
function UserIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/>
      <path d="M4 21a8 8 0 0 1 16 0"/>
    </svg>
  )
}
function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6z"/>
    </svg>
  )
}
function UsersIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  )
}
function PlugIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v6"/>
      <path d="M9 8h6v4a3 3 0 0 1-6 0z"/>
      <path d="M12 14v6"/>
    </svg>
  )
}
function PowerIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
      <line x1="12" y1="2" x2="12" y2="12"/>
    </svg>
  )
}
function ChevronIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  )
}
function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/>
      <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  )
}
function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9"/>
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/>
    </svg>
  )
}
function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
      <path d="M10 11v6M14 11v6"/>
    </svg>
  )
}
function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  )
}
function GIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" style={{ display: 'block' }}>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  )
}
