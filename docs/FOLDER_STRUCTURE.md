# 🗂️ Cấu Trúc Dự Án — Aisha AI Agent

> **Cập nhật:** 2026-04-27  
> **Sprint:** 1–9 ✅ + UI Agent (Sprint 10 đang phát triển)

---

## 📁 Cây Thư Mục Toàn Dự Án

```
LyMinhThuan_AI_Agent/
│
├── 📄 README.md                    # Tài liệu chính, hướng dẫn cài đặt + chạy
├── 📄 requirements.txt             # Python dependencies (backend)
├── 📄 Dockerfile                   # Build FastAPI container
├── 📄 docker-compose.yml           # 4 services: api, nginx, redis, mosquitto
├── 📄 .env / .env.example          # Config biến môi trường
├── 📄 .gitignore
│
├── 📂 src/                         # ── BACKEND (FastAPI) ──────────────────
├── 📂 frontend/                    # ── FRONTEND (React + Capacitor) ───────
├── 📂 docs/                        # ── TÀI LIỆU ────────────────────────────
├── 📂 tests/                       # ── TESTS ───────────────────────────────
├── 📂 monitor/                     # ── PIPELINE DASHBOARD ──────────────────
├── 📂 infrastructure/              # ── DEVOPS (Nginx, Mosquitto, scripts) ──
├── 📂 firmware/                    # ── ESP32 FIRMWARE ──────────────────────
├── 📂 data/                        # ── RUNTIME DATA (users.json, SQLite) ───
├── 📂 static/                      # ── STATIC HTML (test UI) ───────────────
└── 📂 keys/                        # ── JWT RSA KEYS (gitignored) ────────────
```

---

## 📂 src/ — Backend Core (FastAPI)

```
src/
├── __init__.py
├── config.py                       # Pydantic Settings — đọc toàn bộ .env, type-safe
│
├── api/                            # ── HTTP Layer ─────────────────────────
│   ├── app.py                      # FastAPI factory + lifespan context manager
│   ├── middlewares/
│   │   └── auth.py                 # JWT RS256 middleware — inject CurrentUser
│   └── routes/
│       ├── health.py               # GET /health — Docker healthcheck
│       ├── auth.py                 # POST /auth/login|logout, GET /auth/me, POST /auth/google
│       ├── chat.py                 # POST /chat, POST /chat/stream (SSE), POST /chat/confirm
│       ├── voice.py                # POST /voice/tts — Edge TTS HoaiMy + gTTS fallback
│       ├── apps.py                 # GET /apps, POST /apps/execute
│       ├── users.py                # CRUD /users (owner-only)
│       └── monitor.py              # GET /monitor/events (SSE), GET /monitor/history
│
├── core/                           # ── Business Logic ─────────────────────
│   ├── ai_engine/                  # Não bộ AI
│   │   ├── groq_client.py          # Groq API client: chat() + chat_stream() async gen
│   │   ├── intent_parser.py        # Tiếng Việt → JSON intent (regex trước, LLM sau)
│   │   ├── agent.py                # AI Orchestrator — kết nối parser ↔ gateway
│   │   └── siri_brain.py          # Siri Brain: 6 intent categories + response handlers
│   │
│   ├── app_actions/                # Native System Agent (Windows Automation)
│   │   ├── base.py                 # AppProvider abstract base + AppActionResult
│   │   ├── router.py               # Parse intent → dispatch provider/ui_agent ⭐ UPDATED
│   │   ├── providers.py            # 13 providers: Phone, SMS, Zalo, FB, YouTube, Maps...
│   │   ├── system_executor.py      # Mở exe/UWP/folder thật trên Windows
│   │   ├── app_discovery.py        # Auto-scan Registry + Start Menu → tìm exe path
│   │   ├── file_ops.py             # Tạo file/folder (whitelist user folders)
│   │   ├── permissions.py          # Kiểm tra quyền truy cập
│   │   └── ui_agent.py             # 🆕 Generic UI Agent — Vision LLM automation
│   │
│   ├── security/                   # Security Gateway 6 Lớp
│   │   ├── gateway.py              # ★ ORCHESTRATOR — pipeline 8 bước
│   │   ├── sanitizer.py            # Input validation + 10 injection patterns
│   │   ├── rule_engine.py          # Allow-list + deny-list rules
│   │   ├── rbac.py                 # Owner vs Guest permissions
│   │   ├── rate_limiter.py         # Redis Sliding Window + InMemory fallback
│   │   ├── pending_store.py        # Redis SETEX TTL 60s cho confirmation flow
│   │   ├── audit_logger.py         # SQLite WAL + SHA-256 checksum (immutable)
│   │   ├── crypto.py               # AES-256-GCM encrypt/decrypt
│   │   └── vault.py                # EnvVault + InMemoryVault
│   │
│   ├── guardrails/                 # NeMo Guardrails config
│   │   ├── config.yml
│   │   ├── rails.co                # Colang rules
│   │   └── actions.py
│   │
│   └── location/                   # GPS + Reverse Geocoding
│       └── geocoder.py             # Google Maps → Nominatim → raw coords fallback
│
├── services/
│   ├── ha_provider/                # Home Assistant Integration
│   │   ├── ha_client.py            # Async REST client — 23 action mappings
│   │   └── entity_registry.py      # 20+ alias tiếng Việt → HA entity_id
│   └── memory/                     # Encrypted Memory Store
│       ├── encryption.py
│       └── store.py
│
└── tools/
    └── schemas.py                  # Pydantic schemas: Light, Lock, Climate, Switch, Sensor
```

---

## 📂 frontend/ — React + Capacitor (Web + APK Android)

```
frontend/
├── index.html
├── package.json                    # Capacitor 6 + React 19 + Vite 8
├── vite.config.js
├── capacitor.config.json           # appId: vn.aisha.app, webDir: dist
├── .env / .env.example             # VITE_API_URL, VITE_GOOGLE_CLIENT_ID
├── .env.production                 # Auto-generated bởi setup-env.mjs (IP LAN)
│
├── scripts/
│   └── setup-env.mjs               # Auto-detect IP LAN → ghi .env.production
│
├── src/
│   ├── main.jsx
│   ├── App.jsx                     # Layout: header + Bottom Nav, role badge
│   │
│   ├── api/
│   │   ├── client.js               # Axios + JWT interceptor + streamMessage() SSE
│   │   └── config.js               # Dynamic API URL: localStorage → .env → fallback
│   │
│   ├── components/
│   │   └── VoiceOrb.jsx            # Siri Orb — 4 states: idle/listening/thinking/speaking
│   │                               # forwardRef + dual-backend (Web Speech / Capacitor native)
│   │
│   ├── hooks/
│   │   └── useWakeWord.js          # Continuous "Hey Aisha" — Web + APK native, auto-restart
│   │
│   ├── store/
│   │   └── useStore.js             # Zustand: auth, messages, devices, GPS, roles
│   │
│   ├── features/                   # Feature-based modules
│   ├── layouts/                    # Layout wrappers
│   ├── lib/                        # Utilities
│   ├── theme/                      # Design tokens
│   └── ui/                        # UI components
│
├── dist/                           # Vite build output (web deploy)
└── android/                        # (auto-gen) Capacitor Android project → build APK
```

---

## 📂 tests/ — Automated Test Suite

```
tests/
├── conftest.py                     # Bootstrap sys.path
├── unit/
│   ├── test_rate_limiter.py
│   ├── test_security.py
│   ├── test_geocoder.py
│   └── test_groq_keys.py
├── integration/
│   ├── test_api.py
│   ├── test_chat.py
│   ├── test_siri.py
│   └── test_injection.py           # 20 injection vectors → 100% blocked
├── security/
│   ├── test_rule_engine.py
│   ├── test_sanitizer.py
│   └── test_audit_logger.py
└── manual/
    ├── bench.py                    # Benchmark response time
    ├── tts.py                      # Test TTS voices
    └── voices.py
```

---

## 📂 docs/ — Tài Liệu Dự Án

```
docs/
├── SKILL_REPORT.md                 # Sprint 1-9 — tổng kết work done (42KB)
├── QUY_TRINH_LAM_VIEC.md          # Quy trình 6 sprint, Gantt chart, 2 thành viên
├── implementation_planv2.md        # Thiết kế chi tiết từng module
├── SECURITY_ARCHITECTURE.md        # Zero Trust 6 lớp, threat model
├── FRONTEND_DESIGN.md              # React + Capacitor → APK design
├── ANDROID_BUILD.md                # Hướng dẫn build APK đầy đủ (JDK 21, SDK 34)
├── DEPLOYMENT_GUIDE.md             # Deploy production A→Z
├── WORKFLOW.md                     # 5 Mermaid workflow diagrams
└── HUONG_DAN_SU_DUNG.md           # Hướng dẫn cài đặt + sử dụng API
```

---

## 📂 infrastructure/ — DevOps

```
infrastructure/
├── nginx/
│   └── nginx.conf                  # Reverse proxy + rate limit + security headers
├── mosquitto/
│   └── mosquitto.conf              # MQTT TLS-only (port 8883), disable 1883
└── scripts/
    ├── gen_certs.sh                # Tạo CA + server cert + ESP32 client cert
    └── gen_jwt_keys.py             # Tạo RSA 2048-bit key pair (Python, không cần OpenSSL CLI)
```

---

## 📂 monitor/ — Pipeline Dashboard

```
monitor/
├── index.html                      # Standalone HTML dashboard (không dùng React)
├── style.css                       # Tree visualization — 2 branch: Smart Home / App
└── app.js                          # EventSource SSE client + animation theo pipeline step
```

---

## 🏗️ Kiến Trúc Security Gateway (6 Lớp)

```
Request
   │
   ▼
[0] Rate Limiter          ← rate_limiter.py  (Redis Sliding Window + InMemory fallback)
   │
   ▼
[1] Input Sanitizer       ← sanitizer.py     (10 injection patterns, entity_id regex)
   │
   ▼
[2] RBAC Check            ← rbac.py          (Owner: tất cả | Guest: light + sensor)
   │
   ▼
[3] Rule Engine           ← rule_engine.py   (allow-list + deny-list cứng)
   │
   ▼
[4] Confirmation Flow     ← pending_store.py (Redis TTL 60s cho lệnh nguy hiểm)
   │
   ▼
[5] Circuit Breaker       ← rate_limiter.py  (CLOSED→OPEN→HALF_OPEN)
   │
   ▼
[6] Execute               ← ha_client.py     (23 HA mappings) / ui_agent.py (Windows)
   │
   ▼
[7] Audit Logger          ← audit_logger.py  (SQLite WAL + SHA-256, bất biến, immutable)
   │
   ▼
Response → User
```

---

## 🤖 Generic UI Agent — Kiến Trúc Mới (Sprint 10)

> **File:** `src/core/app_actions/ui_agent.py`  
> **Mục tiêu:** Tự động hóa **BẤT KỲ app nào** — không hardcode từng app.

```
User: "Zalo kiếm My Báo gửi My Nguuu"
   │
   ▼
router.py (parse regex) → provider="ui_agent", action="zalo_chat"
   │
   ▼
_execute_ui_agent()
   │
   ▼  Lặp tối đa 12 bước:
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  1. Chụp màn hình (pyautogui.screenshot)                 │
│       ↓ Thu nhỏ 70% (Pillow) → JPEG → base64            │
│                                                          │
│  2. Groq Vision LLM (llama-4-scout-17b):                 │
│     "Nhìn ảnh này, thao tác TIẾP THEO để [goal] là gì?" │
│     → {"action": "click", "x": 450, "y": 120, ...}      │
│                                                          │
│  3. Execute thao tác (pyautogui):                        │
│     click | double_click | type | paste |                │
│     key | hotkey | scroll | wait                         │
│                                                          │
│  4. Nếu action = "done" → RETURN kết quả                 │
│     Ngược lại → quay lại bước 1                          │
│                                                          │
└──────────────────────────────────────────────────────────┘
   │
   ▼
Response: "Đã gửi tin nhắn cho My Báo: My Nguuu"
```

**Ưu điểm so với cách cũ (hardcode từng app):**

| | Hardcode | UI Agent |
|--|:--:|:--:|
| Zalo | ✅ | ✅ |
| Teams, MS Word | ❌ | ✅ |
| App lạ không biết trước | ❌ | ✅ |
| Cần viết code thêm cho app mới | ✅ mỗi app 1 file | ❌ không cần |
| Thích nghi UI thay đổi | ❌ | ✅ |

---

## 🛠️ Tech Stack Tóm Tắt

| Tầng | Công nghệ | Ghi chú |
|------|-----------|---------|
| **AI** | Groq API (llama-3/4, vision) | Free tier, TTFT < 1s |
| **Backend** | FastAPI + Uvicorn | Python 3.10+ |
| **Auth** | JWT RS256 + Google OAuth2 | Asymmetric keys |
| **DB** | SQLite (audit) + Redis (rate limit) | WAL mode, Sorted Set |
| **Smart Home** | Home Assistant REST API | 23 action mappings |
| **Windows Agent** | pyautogui + Vision LLM | Generic, mọi app |
| **Frontend** | React 19 + Vite 8 + Zustand | Siri-like dark UI |
| **Mobile** | Capacitor 6 | APK Android, 1 lệnh build |
| **Voice** | Edge TTS (HoaiMy Neural) | Giọng nữ Việt Neural |
| **Wake-word** | Web Speech API + Capacitor plugin | Dual backend |
| **Proxy** | Nginx | Rate limit + security headers |
| **MQTT** | Mosquitto TLS 1.3 | Port 8883 only |

---

## 📊 Thống Kê Dự Án

| Metric | Giá trị |
|--------|---------|
| Sprints hoàn thành | **9/9 ✅** + Sprint 10 đang phát triển |
| Files tạo/sửa | **95+ files** |
| Tổng dòng code | **~10,500+ lines** |
| Tests passed | **46/46 (100%)** |
| API endpoints | **18 endpoints** |
| Response time | **3ms — 441ms** |
| Providers app | **13 providers** |
| HA action mappings | **23 actions** |

---

*Cập nhật tự động sau mỗi sprint. File gốc: `docs/FOLDER_STRUCTURE.md`*
