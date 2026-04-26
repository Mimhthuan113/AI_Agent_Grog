import axios from 'axios'
import { getApiUrl } from './config'

const api = axios.create()

// Auto-attach JWT token + set baseURL động (cho phép user đổi backend URL runtime)
api.interceptors.request.use(config => {
  config.baseURL = getApiUrl()
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-logout khi token hết hạn (401)
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('roles')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

// Auth
export const login = async (username, password) => {
  const { data } = await api.post('/auth/login', { username, password })
  localStorage.setItem('token', data.access_token)
  return data
}

// Google OAuth2 Login
export const googleLogin = async (credential) => {
  const { data } = await api.post('/auth/google', { credential })
  localStorage.setItem('token', data.access_token)
  return data
}

export const logout = async () => {
  try { await api.post('/auth/logout') } catch { /* idempotent */ }
  localStorage.removeItem('token')
  localStorage.removeItem('roles')
}

export const getMe = async () => {
  const { data } = await api.get('/auth/me')
  return data
}

// Chat
export const sendMessage = async (message) => {
  const { data } = await api.post('/chat', { message })
  return data
}

// ── Streaming chat (SSE) ─────────────────────────────
// Vì axios không stream tốt và EventSource không hỗ trợ POST + custom header,
// dùng fetch + ReadableStream để parse SSE thủ công.
//
// Callback API:
//   onMeta({category, request_id})
//   onChunk(textPiece)
//   onDone({success, command, requires_confirmation, request_id})
//   onError(error)
export const streamMessage = async (
  message,
  { lat = null, lng = null, signal = null, onMeta, onChunk, onDone, onError } = {}
) => {
  const token = localStorage.getItem('token')
  const payload = { message }
  if (lat != null && lng != null) {
    payload.lat = lat
    payload.lng = lng
  }

  let res
  try {
    res = await fetch(`${getApiUrl()}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    })
  } catch (err) {
    onError?.(err)
    throw err
  }

  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('roles')
      window.location.reload()
      return
    }
    const err = new Error(`HTTP ${res.status}`)
    err.status = res.status
    onError?.(err)
    throw err
  }

  if (!res.body || !res.body.getReader) {
    // Browser không hỗ trợ ReadableStream → fallback đọc full text
    const text = await res.text()
    parseSSEBlock(text, { onMeta, onChunk, onDone })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE events tách bằng \n\n
      let sepIdx
      while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, sepIdx)
        buffer = buffer.slice(sepIdx + 2)
        parseSSEBlock(block, { onMeta, onChunk, onDone })
      }
    }
    // Flush phần còn lại (nếu có)
    if (buffer.trim()) parseSSEBlock(buffer, { onMeta, onChunk, onDone })
  } catch (err) {
    if (err.name !== 'AbortError') onError?.(err)
    throw err
  }
}

// Parse 1 block SSE (có thể chứa nhiều dòng "data: ...")
function parseSSEBlock(block, { onMeta, onChunk, onDone }) {
  const lines = block.split('\n')
  for (const line of lines) {
    if (!line.startsWith('data:')) continue
    const json = line.slice(5).trim()
    if (!json) continue
    let evt
    try { evt = JSON.parse(json) } catch { continue }
    if (evt.type === 'meta') onMeta?.(evt)
    else if (evt.type === 'chunk') onChunk?.(evt.text || '')
    else if (evt.type === 'done') onDone?.(evt)
  }
}

// Confirm — xác nhận lệnh nguy hiểm
export const confirmCommand = async (request_id, confirmed) => {
  const { data } = await api.post('/chat/confirm', { request_id, confirmed })
  return data
}

// Devices
export const getDevices = async () => {
  const { data } = await api.get('/devices')
  return data
}

// Audit
export const getAudit = async (limit = 30) => {
  const { data } = await api.get(`/audit?limit=${limit}`)
  return data
}

// ── User Management ──────────────────────────
export const listUsers = async () => {
  const { data } = await api.get('/users')
  return data
}

export const createUser = async (username, password, display_name, role) => {
  const { data } = await api.post('/users', { username, password, display_name, role })
  return data
}

export const deleteUser = async (username) => {
  const { data } = await api.delete(`/users/${username}`)
  return data
}

export const updateUser = async (username, updates) => {
  const { data } = await api.put(`/users/${username}`, updates)
  return data
}

export default api
