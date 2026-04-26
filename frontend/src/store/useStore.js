import { create } from 'zustand'

const useStore = create((set, get) => ({
  // Auth
  user: null,
  token: localStorage.getItem('token') || null,
  roles: JSON.parse(localStorage.getItem('roles') || '[]'),
  displayName: localStorage.getItem('displayName') || '',
  picture: localStorage.getItem('picture') || '',

  setAuth: (user, token) => {
    localStorage.setItem('token', token)
    localStorage.setItem('roles', JSON.stringify(user?.roles || []))
    localStorage.setItem('displayName', user?.display_name || user?.user_id || '')
    localStorage.setItem('picture', user?.picture || '')
    set({
      user,
      token,
      roles: user?.roles || [],
      displayName: user?.display_name || user?.user_id || '',
      picture: user?.picture || '',
    })
  },

  clearAuth: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('roles')
    localStorage.removeItem('displayName')
    localStorage.removeItem('picture')
    set({ user: null, token: null, roles: [], displayName: '', picture: '', messages: [WELCOME_MSG()] })
  },

  // Role helpers
  isOwner: () => get().roles.includes('owner'),
  isGuest: () => get().roles.includes('guest'),

  // Chat
  messages: [WELCOME_MSG()],
  addMessage: (msg) => set(s => ({ messages: [...s.messages, msg] })),
  // Patch (merge) message cuối cùng — dùng cho streaming SSE update text dần
  updateLastMessage: (patch) => set(s => {
    if (!s.messages.length) return {}
    const last = s.messages[s.messages.length - 1]
    return { messages: [...s.messages.slice(0, -1), { ...last, ...patch }] }
  }),
  isThinking: false,
  setThinking: (v) => set({ isThinking: v }),

  // Confirmation Flow
  pendingConfirm: null,  // {request_id, command, message}
  setPendingConfirm: (p) => set({ pendingConfirm: p }),

  // Devices
  devices: [],
  setDevices: (d) => set({ devices: d }),

  // Active page
  activePage: 'chat',
  setPage: (p) => set({ activePage: p }),

  // Geolocation — vị trí GPS real-time
  location: null,  // {lat, lng, accuracy}
  locationError: null,
  _watchId: null,
  requestLocation: () => {
    if (!navigator.geolocation) {
      set({ locationError: 'Trình duyệt không hỗ trợ GPS.' });
      return;
    }
    // Dùng watchPosition thay vì getCurrentPosition — cập nhật liên tục
    const existing = get()._watchId;
    if (existing) return; // Đã đang watch rồi

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const loc = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        };
        console.log('[GPS] Updated:', loc.lat.toFixed(4), loc.lng.toFixed(4), '±', Math.round(loc.accuracy) + 'm');
        set({ location: loc, locationError: null });
      },
      (err) => {
        console.warn('[GPS] Error:', err.message);
        set({ locationError: err.message });
        // Auto-retry sau 5s nếu bị deny
        if (err.code === 1) { // PERMISSION_DENIED
          console.log('[GPS] Permission denied — sẽ thử lại khi user cho phép');
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }
    );
    set({ _watchId: watchId });
  },
}))

function WELCOME_MSG() {
  return {
    id: 'welcome',
    role: 'ai',
    text: 'Xin chào! Tôi là Aisha 💁‍♀️\nTrợ lý nhà thông minh của bạn. Hãy nói hoặc gõ lệnh bằng tiếng Việt.',
    time: new Date().toISOString(),
  }
}

export default useStore

