# 🛠️ Skill Report — Những Gì Đã Làm Được

> **Ngày:** 2026-04-22  
> **Session:** Sprint 1 + Sprint 2 + Sprint 3 + Sprint 4 ✅  
> **Thời gian làm việc:** ~4 giờ  
> **Cập nhật lần cuối:** 2026-04-22 02:54

---

## Tổng Quan

Đã xây dựng **backend + frontend hoàn chỉnh** cho dự án Smart AI Home Hub (tên sản phẩm: **Aisha**) — bao gồm hệ thống bảo mật 4 lớp, tích hợp AI (Groq LLM), Voice Assistant giọng nữ Neural, và giao diện React Siri-like.

### Thống kê

| Metric | Giá trị |
|--------|---------|
| Files tạo/sửa | **45+ files** |
| Tổng dòng code | **~4,500 lines** |
| Tests viết | **26 test cases** |
| Tests passed | **26/26 (100%)** |
| Sprints hoàn thành | **4 / 6** |
| API endpoints | **8 endpoints** |
| Frontend pages | 4 pages (React) |
| Response time | **3ms — 441ms** |

---

## Sprint 1 — Foundation & Auth ✅ DONE (8/8 tests)

### Files đã tạo

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/config.py` | Pydantic Settings — đọc toàn bộ .env, type-safe | ~150 |
| `src/api/app.py` | FastAPI app factory — CORS, startup logging | ~90 |
| `src/api/routes/health.py` | `GET /health` — Docker healthcheck | ~30 |
| `src/api/routes/auth.py` | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | ~210 |
| `src/api/middlewares/auth.py` | JWT RS256 validation, Redis blacklist | ~180 |
| `infrastructure/scripts/gen_jwt_keys.py` | Tạo RSA key pair bằng Python (không cần openssl CLI) | ~48 |
| 11 × `__init__.py` | Python package init cho tất cả folders | 11 |

### Tính năng hoàn thành

- ✅ JWT RS256 authentication (asymmetric keys)
- ✅ Login endpoint trả JWT token (15 phút)
- ✅ Logout endpoint + Redis blacklist (jti)
- ✅ JWT middleware inject `CurrentUser` vào routes
- ✅ 5 validation cases: valid / expired / tampered / missing / blacklisted
- ✅ Fail-close trong production, fail-open trong dev
- ✅ Không lộ lý do reject cụ thể (chống enumeration)

### API Endpoints Sprint 1

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| GET | `/health` | ❌ | Health check |
| POST | `/auth/login` | ❌ | Đăng nhập → JWT |
| POST | `/auth/logout` | ✅ | Thu hồi token |
| GET | `/auth/me` | ✅ | Thông tin user |

---

## Sprint 2 — Security Gateway ✅ DONE (18/18 tests)

### Files đã tạo

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/tools/schemas.py` | Pydantic schemas cho 5 loại thiết bị | ~140 |
| `src/core/security/sanitizer.py` | Input validation + 10 injection detection patterns | ~180 |
| `src/core/security/audit_logger.py` | SQLite WAL, immutable triggers, SHA-256 checksums | ~240 |
| `src/core/security/vault.py` | EnvVault + InMemoryVault + factory pattern | ~110 |
| `src/core/security/gateway.py` | Security orchestrator (sanitize→rule→execute→audit) | ~280 |

### Tính năng hoàn thành

- ✅ **5 Pydantic Schemas**: Light, Switch, Lock, Climate, Sensor
  - LockCommand CHỈ có `lock` — không có `unlock` (double defense)
  - Brightness: 0-255, Temperature: 16.0-30.0
- ✅ **Sanitizer** với 10 regex injection patterns
  - Phát hiện: "ignore rules", "system prompt", "bypass security"...
  - Validate entity_id regex: `^[a-z_]+\.[a-z0-9_]+$`
  - Error codes user-friendly, không lộ stack trace
- ✅ **Audit Logger** bất biến
  - SQLite WAL mode (concurrent reads)
  - `BEFORE UPDATE` trigger → ABORT
  - `BEFORE DELETE` trigger → ABORT
  - SHA-256 checksum cho mỗi record
  - `verify_integrity()` để phát hiện tampering
- ✅ **Security Gateway** orchestrator
  - Pipeline: Sanitize → Rule Engine → Execute → Audit
  - Không có đường tắt bypass
  - Catch-all error handler — gateway KHÔNG BAO GIỜ crash
  - Audit log LUÔN được ghi, kể cả khi reject

### Test Results Sprint 2

```
 4 schema tests       → PASSED
 5 sanitizer tests    → PASSED
 4 rule engine tests  → PASSED
 4 gateway tests      → PASSED
 1 audit verify test  → PASSED
─────────────────────────────
18/18 = 100% PASSED
```

---

## Sprint 3 — AI Engine & Chat API ✅ DONE

### Files đã tạo — Backend

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/core/ai_engine/groq_client.py` | Groq API client + exponential backoff retry | ~160 |
| `src/core/ai_engine/intent_parser.py` | Tiếng Việt → JSON command (LLM + fallback regex) | ~170 |
| `src/core/ai_engine/agent.py` | AI orchestrator — kết nối parser với gateway | ~160 |
| `src/services/ha_provider/entity_registry.py` | 20+ alias tiếng Việt → HA entity_id | ~170 |
| `src/api/routes/chat.py` | `POST /chat`, `GET /devices`, `GET /audit` | ~120 |

### Files đã tạo — Test UI (HTML tĩnh)

| File | Mô tả | Lines |
|------|--------|:-----:|
| `static/index.html` | Giao diện test nhanh — dark theme, 3 tab (Chat/Devices/History) | ~420 |

### Files đã tạo — Frontend React Siri-like

| File | Mô tả | Lines |
|------|--------|:-----:|
| `frontend/src/api/client.js` | Axios instance + JWT interceptor | ~55 |
| `frontend/src/store/useStore.js` | Zustand state (auth, messages, devices, nav) | ~35 |
| `frontend/src/App.jsx` + `.css` | Layout chính: header (Siri mini orb) + bottom nav | ~200 |
| `frontend/src/pages/LoginPage.jsx` + `.css` | Login — animated Siri orb, glassmorphism card | ~200 |
| `frontend/src/pages/ChatPage.jsx` + `.css` | Chat — quick commands, AI orb avatar, thinking dots | ~300 |
| `frontend/src/pages/DevicesPage.jsx` + `.css` | Grid thiết bị — responsive 2/3/4 cột | ~130 |
| `frontend/src/pages/HistoryPage.jsx` + `.css` | Audit log — color-coded APPROVED/DENIED | ~150 |
| `frontend/src/index.css` | Global dark theme + gradient orbs + animations | ~100 |
| `frontend/.env` | `VITE_API_URL=http://localhost:8000` | 1 |

### Tính năng hoàn thành

- ✅ **Groq Client** với retry logic
  - Exponential backoff: 1s → 2s → 4s khi gặp 429
  - Timeout protection
  - Không log API key
- ✅ **Entity Registry** — 20+ alias tiếng Việt
  - "đèn phòng ngủ" → `light.phong_ngu`
  - "bếp" → `switch.kitchen_stove`
  - "khóa cửa" → `lock.cua_chinh`
  - Fuzzy matching + accent stripping
- ✅ **Intent Parser** — dual mode
  - Primary: LLM (Groq) parse tiếng Việt
  - Fallback: regex + registry (khi LLM fail)
- ✅ **AI Agent** — main orchestrator
  - Mọi lệnh đi qua Security Gateway
  - Response tiếng Việt user-friendly
  - Confirmation flow cho WARNING actions
- ✅ **Chat API** — 3 endpoints mới
- ✅ **Test UI** (static/index.html) — dark theme, chat + devices + history
- ✅ **React Frontend Siri-like** — premium dark UI
  - Siri gradient orb trên login & chat
  - Glassmorphism cards
  - Zustand state management
  - Axios JWT auto-attach
  - Bottom navigation (3 tabs)
  - Quick command pills
  - Responsive device grid
  - Color-coded audit history

### API Endpoints Sprint 3

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| POST | `/chat` | ✅ | Gửi lệnh tiếng Việt |
| GET | `/devices` | ✅ | Danh sách thiết bị |
| GET | `/audit` | ✅ | Lịch sử lệnh |

### Design Style — Siri-like

```
Thiết kế lấy cảm hứng từ Apple Siri:
- Gradient orb animation (purple → pink → cyan)
- Glassmorphism (backdrop-filter: blur)
- Dark bg (#050510) + subtle gradient orbs
- Micro-animations: pulse, fadeIn, orbFloat
- Font: Inter (Google Fonts)
- Bottom navigation giống native app
- Responsive: 2 cột mobile → 4 cột desktop
```

---

## Sprint 4 — Aisha Voice Assistant ✅ DONE

### 4A. Rebranding → Aisha

Đổi tên toàn bộ hệ thống từ "Smart Home AI" sang **Aisha** (AI Smart Home Assistant).

| File | Thay đổi |
|------|----------|
| `frontend/src/App.jsx` | Header title → "Aisha" |
| `frontend/src/pages/LoginPage.jsx` | Login title → "Aisha" |
| `frontend/index.html` | Browser tab → "Aisha — Trợ lý nhà thông minh" |
| `frontend/src/store/useStore.js` | Welcome message → Aisha self-intro |
| `src/core/ai_engine/siri_brain.py` | System prompt, persona, responses → Aisha |
| `src/core/guardrails/rails.co` | Guardrail bot responses → Aisha |

### 4B. Voice Engine — Edge TTS (HoaiMy Neural)

**Vấn đề:** Web Speech API chỉ có giọng nam mặc định → không phù hợp persona nữ.

**Giải pháp:** Server-side TTS sử dụng `edge-tts` → giọng **`vi-VN-HoaiMyNeural`** (nữ, Neural, tự nhiên). Fallback `gTTS` (Google TTS nữ Việt) khi Edge TTS lỗi network.

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/api/routes/voice.py` | **[NEW]** Endpoint `/voice/tts` — Edge TTS + gTTS fallback | ~95 |
| `src/api/app.py` | Register voice router | sửa |
| `frontend/src/components/VoiceOrb.jsx` | Frontend TTS — fetch MP3 → Audio play | sửa |

**Flow:**
```
User nói → Frontend POST /chat → Backend trả text
                               → Frontend POST /voice/tts
                               → Backend Edge TTS (HoaiMy) → MP3
                               → Fallback gTTS nếu Edge fail
                               → Frontend play Audio
```

### 4C. Siri-style UI Redesign

| File | Mô tả | Lines |
|------|--------|:-----:|
| `frontend/src/components/VoiceOrb.css` | **[REWRITE]** Siri orb — 4 states, rainbow conic gradient | ~220 |
| `frontend/src/pages/ChatPage.css` | **[REWRITE]** Centered orb layout, suggestion chips | ~240 |
| `frontend/src/pages/ChatPage.jsx` | **[REWRITE]** Siri layout, response card, chip suggestions | ~175 |
| `frontend/src/App.css` | Compact header | sửa |

**Orb States:**
```
├── Idle     → Tím gradient + float animation + rainbow glow mờ
├── Listening → Xanh lá + wave bars + glow nhanh
├── Thinking  → Tím đậm + 3 dots bounce + glow sáng
└── Speaking  → Xanh dương + pulse circle + rainbow xoay nhanh
```

### 4D. Performance Optimization

#### Root Cause #1: Redis timeout (6s → 0ms)
Mỗi request chờ Redis TCP timeout 6s. Fix: cache failure 60s + socket timeout 0.3s.

| File | Thay đổi |
|------|----------|
| `src/api/middlewares/auth.py` | `_redis_failed` cache + `socket_connect_timeout=0.3` |

#### Root Cause #2: LLM-first intent parsing (8s → 17ms)
Smart home commands gọi LLM trước (5-8s) rồi mới fallback regex.

| File | Thay đổi |
|------|----------|
| `src/core/ai_engine/intent_parser.py` | Regex trước (tức thì), LLM sau (chỉ khi regex fail) |

#### Root Cause #3: Thiếu instant patterns
"Cảm ơn", "Tạm biệt", "Bạn đẹp quá" → general_chat → gọi LLM chậm.

| File | Thay đổi |
|------|----------|
| `src/core/ai_engine/siri_brain.py` | +3 IntentCategory (THANKS, GOODBYE, COMPLIMENT) |
|  | +3 pattern matchers + response handlers tức thì |
|  | LLM timeout 3s + max_tokens 150 cho general_chat |

### Benchmark Results Sprint 4

```
============================================================
BENCHMARK — Response Time (persistent client, sau warmup)
============================================================
✅ [0.003s] greeting             | Xin chào
✅ [0.003s] time                 | Mấy giờ rồi
✅ [0.003s] self_intro           | Tên bạn là gì
✅ [0.017s] smart_home           | Bật đèn phòng ngủ
✅ [0.004s] thanks               | Cảm ơn bạn
✅ [0.004s] goodbye              | Tạm biệt
✅ [0.003s] compliment           | Bạn dễ thương quá
✅ [0.013s] smart_home           | Tắt quạt phòng khách
✅ [0.441s] general_chat (LLM)   | Kể chuyện cười đi
============================================================
9/9 = 100% UNDER 2s ✅
```

| Metric | Trước | Sau | Cải thiện |
|--------|:-----:|:---:|:---------:|
| Greeting | 6.5s | 3ms | **99.95%** |
| Smart home | 8.5s | 17ms | **99.8%** |
| General (LLM) | 10s+ | 441ms | **95.6%** |
| Max timeout | ∞ | 3s | **Bounded** |

### API Endpoints Sprint 4

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| POST | `/voice/tts` | ✅ | Text-to-Speech (Edge TTS HoaiMy / gTTS fallback) |

---

## Tài Liệu Đã Tạo

| File | Mô tả |
|------|--------|
| `docs/QUY_TRINH_LAM_VIEC.md` | Quy trình 6 Sprint, phân chia 2 người, Gantt chart |
| `docs/HUONG_DAN_SU_DUNG.md` | Hướng dẫn cài đặt + sử dụng API + troubleshooting |
| `docs/SKILL_REPORT.md` | File này — tổng kết work done |

---

## Sơ Đồ Kiến Trúc Đã Implement

```
User Request (tiếng Việt)
    │
    ▼
[POST /chat] ← JWT Auth Middleware (RS256)
    │
    ▼
[AI Agent] ← agent.py
    │
    ├──→ [Intent Parser] ← intent_parser.py
    │       ├── LLM (Groq API) ← groq_client.py
    │       └── Fallback (regex + registry) ← entity_registry.py
    │
    ▼
[Security Gateway] ← gateway.py ★ QUAN TRỌNG NHẤT
    │
    ├── [1] Sanitizer ← sanitizer.py
    │       └── Regex validate + injection detect
    │
    ├── [2] Rule Engine ← rule_engine.py
    │       └── Allow-list + deny-list check
    │
    ├── [3] Execute ← (HA client — Phase 2)
    │       └── Mock response hiện tại
    │
    └── [4] Audit Logger ← audit_logger.py
            └── SQLite WAL + SHA-256 checksum
    │
    ▼
Response (tiếng Việt) → User
```

---

## Còn Lại Cần Làm

### Sprint 5 — HA Integration & Testing
- [ ] `ha_client.py` — kết nối Home Assistant thật
- [x] ~~MQTT over TLS cho ESP32~~ → **ĐÃ LÀM** (mosquitto.conf + cert gen script)
- [x] ~~NeMo Guardrails config~~ → **ĐÃ LÀM** (config.yml + rails.co + actions.py)
- [x] ~~20 prompt injection vectors~~ → **20/20 PASSED (100%)**
- [ ] Full integration test suite (end-to-end with Docker)
- [ ] Confirmation flow cho lệnh nguy hiểm (mở khóa cửa)

### Sprint 6 — Hardening & Deploy
- [x] ~~Docker Compose~~ → **ĐÃ LÀM** (4 services + 3 networks)
- [x] ~~Nginx reverse proxy~~ → **ĐÃ LÀM** (rate limit + security headers)
- [ ] Sửa Redis container (Docker Compose) — hiện bị lỗi kết nối
- [ ] Rate limiter + Circuit breaker (Redis)
- [ ] AES-256-GCM encryption
- [ ] Langfuse LLM tracing
- [x] ~~Frontend (React + Capacitor → APK)~~ → **ĐÃ LÀM React Siri-like**
- [ ] Capacitor build → APK Android
- [ ] Voice activation ("Hey Aisha")
- [ ] Streaming response (SSE) cho general_chat
- [ ] ESP32 Failsafe Firmware (cần board thật)
- [ ] DEPLOYMENT_GUIDE.md

---

## Dependencies Đã Cài

### Backend (Python)
```
fastapi, uvicorn, pydantic, pydantic-settings,
PyJWT, bcrypt, passlib, cryptography,
httpx, redis, aiosqlite, python-dotenv, python-multipart,
edge-tts, gTTS
```

### Frontend (Node.js)
```
react, react-dom, vite, axios, zustand, react-router-dom
```

---

## Changelog

| Thời gian | Công việc |
|-----------|-----------|
| 22:00 - 23:00 | Sprint 1 (Auth) + Sprint 2 (Security Gateway) |
| 23:00 - 23:30 | Sprint 3 Backend (AI Engine + Chat API) |
| 23:30 - 23:50 | Test UI tĩnh (static/index.html) |
| 23:50 - 00:30 | Frontend test + debug + git push |
| 00:30 - 00:59 | React Frontend Siri-like (4 pages) |
| 01:06 - 01:10 | Docker Compose + Dockerfile + .dockerignore |
| 01:10 - 01:12 | Nginx reverse proxy (rate limit + security headers) |
| 01:10 - 01:12 | Mosquitto MQTT TLS config + cert generator |
| 01:12 - 01:14 | NeMo Guardrails config (config.yml + rails.co + actions.py) |
| 01:14 - 01:17 | Integration Tests: 20 injection vectors → **20/20 PASSED** |
| 01:17 - 01:50 | Sprint 4A: Rebranding → Aisha (6 files) |
| 01:50 - 02:10 | Sprint 4B: Siri Brain — 6 intent categories + handlers |
| 02:10 - 02:20 | Sprint 4B: Edge TTS HoaiMy Neural + gTTS fallback |
| 02:20 - 02:34 | Sprint 4C: Siri-style UI Redesign (orb + chips + centered layout) |
| 02:34 - 02:52 | Sprint 4D: Performance Optimization (6.5s → 3ms) |

---

*Report cập nhật liên tục — mỗi lần làm thêm tính năng sẽ ghi lại ở đây*


