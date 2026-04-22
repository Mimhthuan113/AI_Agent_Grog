import { create } from 'zustand'

const useStore = create((set) => ({
  // Auth
  user: null,
  token: localStorage.getItem('token') || null,
  setAuth: (user, token) => set({ user, token }),
  clearAuth: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null })
  },

  // Chat
  messages: [
    {
      id: 'welcome',
      role: 'ai',
      text: 'Xin chào! Tôi là Aisha 💁‍♀️\nTrợ lý nhà thông minh của bạn. Hãy nói hoặc gõ lệnh bằng tiếng Việt.',
      time: new Date().toISOString(),
    }
  ],
  addMessage: (msg) => set(s => ({ messages: [...s.messages, msg] })),
  isThinking: false,
  setThinking: (v) => set({ isThinking: v }),

  // Devices
  devices: [],
  setDevices: (d) => set({ devices: d }),

  // Active page
  activePage: 'chat',
  setPage: (p) => set({ activePage: p }),
}))

export default useStore
