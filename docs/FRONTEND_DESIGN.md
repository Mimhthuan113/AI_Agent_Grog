# 📱 Smart AI Home Hub — Frontend Design
# React 18 + Vite + Capacitor → Build APK thật

> **Phiên bản:** v2.0  
> **Ngày:** 2026-04-19  
> **Stack:** React 18 + Vite + Tailwind CSS + **Capacitor**  
> **Output:** APK cài trực tiếp (Android) + Web app (PC) — **1 codebase**

---

## 1. Tại sao Capacitor?

> **Capacitor** = viết React bình thường → chạy 1 lệnh → ra file **APK thật** cài trực tiếp trên Android, không cần lên Store.

| Tiêu chí | PWA | **Capacitor** |
|----------|-----|--------------|
| Cài trên Android | ⚠️ Qua browser | ✅ **APK thật, cài offline** |
| Cài trên PC | ✅ Web | ✅ Web |
| Một codebase | ✅ | ✅ |
| Truy cập Camera | ❌ Hạn chế | ✅ Native API |
| Notification | ❌ | ✅ |
| Chi phí | $0 | **$0** |
| Cần Android Studio | ❌ | ✅ (chỉ khi build APK) |

**Luồng:**
```
Viết React → npm run build → npx cap sync → Android Studio → APK ✅
```

---

## 2. Màn hình ứng dụng

```
4 màn hình chính:

┌─────────────────┐
│   Login Screen  │  ← Đăng nhập JWT
├─────────────────┤
│   Chat Screen   │  ← Nhập lệnh tiếng Việt (MÀN HÌNH CHÍNH)
├─────────────────┤
│ Devices Screen  │  ← Xem trạng thái thiết bị
├─────────────────┤
│  History Screen │  ← Lịch sử lệnh (audit log)
└─────────────────┘
```

### Chat Screen

```
┌──────────────────────────────────┐
│ 🏠 Smart Home               🔔  │
├──────────────────────────────────┤
│                                  │
│  [AI] Xin chào! Tôi có thể      │
│       giúp gì cho bạn?           │
│                                  │
│  [User] Tắt đèn phòng ngủ       │
│                                  │
│  [AI] ✅ Đã tắt đèn phòng ngủ   │
│                                  │
│  [User] Bật điều hòa 25 độ      │
│                                  │
│  [AI] ⚠️ Xác nhận bật điều hòa? │
│       [Xác nhận]   [Hủy]        │
│                                  │
├──────────────────────────────────┤
│ 🎤  [Nhập lệnh...]          ➤  │
└──────────────────────────────────┘
```

### Devices Screen

```
┌──────────────────────────────────┐
│ ← Thiết bị                       │
├──────────────────────────────────┤
│ 💡 Đèn phòng ngủ      [●──] OFF │
│ 💡 Đèn phòng khách    [──●] ON  │
│ ❄️ Điều hòa           [●──] OFF │
│ 🔒 Khóa cửa chính     [LOCKED]  │
│ 🌡️ Nhiệt độ phòng     28°C      │
└──────────────────────────────────┘
```

---

## 3. Tech Stack

| Package | Mục đích |
|---------|---------|
| **React 18** | UI framework |
| **Vite 5** | Build tool nhanh |
| **Tailwind CSS** | Responsive mobile-first |
| **Capacitor** | Đóng gói → APK Android |
| **Axios** | Gọi FastAPI backend |
| **Zustand** | State (đơn giản hơn Redux) |
| **React Router 6** | Điều hướng màn hình |

---

## 4. Cấu trúc thư mục

```
frontend/
├── android/                         ← Capacitor tự tạo
│   └── app/build/outputs/apk/debug/
│       └── app-debug.apk            ← FILE APK ĐỂ CÀI ✅
│
├── src/
│   ├── api/
│   │   ├── auth.js          ← login(), logout()
│   │   ├── chat.js          ← sendMessage()
│   │   └── devices.js       ← getDevices()
│   ├── components/
│   │   ├── ChatBubble.jsx
│   │   ├── DeviceCard.jsx
│   │   └── ConfirmDialog.jsx
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── ChatPage.jsx     ← Màn hình chính
│   │   ├── DevicesPage.jsx
│   │   └── HistoryPage.jsx
│   ├── store/useStore.js    ← Zustand
│   ├── App.jsx
│   └── main.jsx
│
├── capacitor.config.js
├── vite.config.js
├── package.json
└── .env                     ← VITE_API_URL=http://192.168.1.x:8000
```

---

## 5. Cài đặt từng bước

### Bước 1 — Tạo React app

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install axios zustand react-router-dom
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Bước 2 — Cài Capacitor

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android

# Khởi tạo (điền tên app và package)
npx cap init "Smart Home Hub" "com.smarthome.hub"
```

### Bước 3 — Build React + Sync vào Android

```bash
# Build React → thư mục dist/
npm run build

# Tạo thư mục android/ (chỉ chạy 1 lần đầu)
npx cap add android

# Sync code mới vào android project
npx cap sync android
```

### Bước 4 — Build APK bằng Android Studio

```bash
# Mở Android Studio
npx cap open android
```

```
Trong Android Studio:
→ Build → Build Bundle(s) / APK(s) → Build APK(s)
→ Đợi 2-3 phút
→ File APK ở: android/app/build/outputs/apk/debug/app-debug.apk ✅
```

### Bước 5 — Cài APK lên điện thoại

```
Cách 1 — Cắm USB:
  Android Studio → Run ▶ → Chọn điện thoại → OK

Cách 2 — Gửi file:
  Copy app-debug.apk → gửi qua Zalo/Telegram/Drive
  Điện thoại mở file → Cài đặt
  (Cho phép "Cài từ nguồn không xác định" nếu hỏi)
```

---

## 6. `capacitor.config.js`

```js
const config = {
  appId: 'com.smarthome.hub',
  appName: 'Smart Home Hub',
  webDir: 'dist',        // Output của Vite
  server: {
    // Để trống = app tự host trong APK
    // Bật dòng dưới khi dev để live-reload
    // url: 'http://192.168.1.100:5173',
    // cleartext: true
  }
}

export default config;
```

> ⚠️ **Quan trọng:**  
> APK gọi backend qua **IP nội bộ** (ví dụ `192.168.1.100:8000`).  
> Điện thoại và máy tính **phải cùng WiFi**.  
> Khi demo → bật hotspot máy tính → điện thoại kết vào.

---

## 7. Code kết nối Backend

```js
// src/api/auth.js
import axios from 'axios'

// Lấy từ .env  →  VITE_API_URL=http://192.168.1.100:8000
const API = import.meta.env.VITE_API_URL

export const login = async (username, password) => {
  const res = await axios.post(`${API}/auth/login`, { username, password })
  localStorage.setItem('token', res.data.access_token)
  return res.data
}

export const getAuthHeader = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
})
```

```js
// src/api/chat.js
export const sendMessage = async (message) => {
  const res = await axios.post(
    `${API}/chat`,
    { message },
    getAuthHeader()
  )
  // { response: "Đã tắt đèn ✅", requires_confirmation: false }
  return res.data
}
```

---

## 8. Chạy trên PC

```bash
# Dev mode — test trên browser luôn, không cần build APK
npm run dev
# → http://localhost:5173

# Build production cho web
npm run build
# → dist/ → serve bằng Nginx
```

---

## 9. Workflow tổng thể

```
Viết React thường (src/)
        │
   ┌────┴────┐
   │         │
   ▼         ▼
npm run dev  npm run build
(browser)    → dist/
                  │
             npx cap sync
                  │
           Android Studio
                  │
            Build APK
                  │
      ┌───────────┴───────────┐
      ▼                       ▼
Cài trên điện thoại      Chạy Web trên PC
(app-debug.apk)          (browser / Nginx)
```

---

## 10. Docker — Thêm service frontend

```yaml
# docker-compose.yml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile    # Build React → Nginx
    ports:
      - "80:80"
    networks:
      - frontend_net
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

---

## 11. Summary Stack Hoàn Chỉnh (v2.4)

```
FRONTEND:
├── React 18 + Vite          ← Quen, phổ biến
├── Tailwind CSS             ← Responsive
├── Capacitor                ← → APK Android thật
├── Zustand                  ← State đơn giản
└── Axios                    ← HTTP client

BACKEND:
├── FastAPI + Pydantic v2    ← Web API
├── LangChain + Groq API     ← AI (quen thuộc)
├── Custom Middleware         ← Chống injection (tự viết)
├── PyJWT + bcrypt           ← Auth
├── Redis                    ← Rate limit + blacklist
├── SQLite WAL               ← Audit log bất biến
└── python-dotenv            ← Secrets

INFRA:
├── Nginx                    ← Serve web + proxy API
├── Mosquitto                ← MQTT broker TLS
└── Docker Compose           ← 1 lệnh chạy tất cả

HARDWARE:
├── ESP32 + ESP-IDF          ← Firmware
├── MQTT TLS                 ← Kết nối an toàn
└── Failsafe State Machine   ← Tắt relay khi mất mạng
```
