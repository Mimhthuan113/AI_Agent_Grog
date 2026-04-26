// ============================================================
// Dynamic API URL Config
// ------------------------------------------------------------
// Khi build APK Capacitor, frontend chạy trong WebView với origin
// `capacitor://localhost`. Lúc đó `localhost:8000` KHÔNG trỏ về máy
// chạy backend nữa → cần URL có IP LAN thật.
//
// Priority:
//   1. localStorage 'aisha:apiUrl'         → user override runtime (Settings UI)
//   2. import.meta.env.VITE_API_URL        → build-time env (.env.production)
//   3. fallback 'http://localhost:8000'    → dev web mặc định
// ============================================================

const STORAGE_KEY = 'aisha:apiUrl'
const FALLBACK = 'http://localhost:8000'

/** Lấy URL backend hiện tại (mỗi lần đọc → cho phép override runtime). */
export function getApiUrl() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && /^https?:\/\//i.test(stored)) return stored.replace(/\/+$/, '')
  } catch { /* private mode? */ }
  const env = import.meta.env.VITE_API_URL
  if (env && /^https?:\/\//i.test(env)) return env.replace(/\/+$/, '')
  return FALLBACK
}

/** Ghi đè URL backend (lưu localStorage). Truyền '' / null → reset về env/default. */
export function setApiUrl(url) {
  if (!url) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  const trimmed = url.trim().replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error('URL phải bắt đầu bằng http:// hoặc https://')
  }
  localStorage.setItem(STORAGE_KEY, trimmed)
}

/** True nếu user đã override URL runtime (vs dùng build env). */
export function hasUserApiOverride() {
  try { return !!localStorage.getItem(STORAGE_KEY) } catch { return false }
}

/** Phát hiện đang chạy trong native Capacitor app (Android/iOS). */
export function isCapacitorNative() {
  if (typeof window === 'undefined') return false
  // 1) Capacitor inject window.Capacitor.isNativePlatform khi nạp plugin core
  const cap = window.Capacitor
  if (cap && typeof cap.isNativePlatform === 'function') {
    try { return cap.isNativePlatform() } catch { /* ignore */ }
  }
  // 2) Heuristic theo origin scheme
  const origin = window.location?.origin || ''
  return origin.startsWith('capacitor://') || origin.startsWith('https://localhost')
}

/** Quick health check: kiểm tra URL có serve API không (timeout 3s). */
export async function pingApiUrl(url) {
  const target = (url || getApiUrl()).replace(/\/+$/, '')
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 3000)
  try {
    const resp = await fetch(`${target}/`, { method: 'GET', signal: controller.signal })
    return resp.ok || resp.status === 404 // 404 cũng coi là server up (chỉ thiếu route)
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}
