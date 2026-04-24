import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: API })

// Auto-attach JWT token
api.interceptors.request.use(config => {
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
  try { await api.post('/auth/logout') } catch (e) {}
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
