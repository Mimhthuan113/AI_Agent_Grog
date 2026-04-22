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

// Auth
export const login = async (username, password) => {
  const { data } = await api.post('/auth/login', { username, password })
  localStorage.setItem('token', data.access_token)
  return data
}

export const logout = async () => {
  try { await api.post('/auth/logout') } catch (e) {}
  localStorage.removeItem('token')
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

export default api
