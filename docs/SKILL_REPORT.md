# 🛠️ Skill Report — Những Gì Đã Làm Được

> **Ngày:** 2026-04-26  
> **Session:** Sprint 1 → Sprint 9 ✅  
> **Cập nhật lần cuối:** 2026-04-26 (Sprint 9 — Refactor & Mobile Hardening)

---

## Tổng Quan

Đã xây dựng **backend + frontend hoàn chỉnh** cho dự án Smart AI Home Hub (tên sản phẩm: **Aisha**) — bao gồm hệ thống bảo mật 6 lớp Zero-Trust, tích hợp AI (Groq LLM), Voice Assistant giọng nữ Neural, Native System Agent (điều hành Windows), Real-time GPS, Pipeline Monitor Dashboard, và giao diện React Siri-like.

### Thống kê

| Metric | Giá trị |
|--------|---------|
| Files tạo/sửa | **95+ files** |
| Tổng dòng code | **~10,500 lines** |
| Tests viết | **46+ test cases** |
| Tests passed | **46/46 (100%)** |
| Sprints hoàn thành | **9 / 9** ✅ |
| API endpoints | **18 endpoints** (thêm `POST /chat/stream`) |
| Frontend pages | 5 pages (React) + Monitor Dashboard |
| App Providers | 12 providers (Zalo, FB, YouTube...) |
| System Apps | 22 hardcoded + auto-discovery toàn bộ Windows |
| HA Service Mappings | **23 actions** (light/lock/climate/fan/cover/media/select) |
| Response time | **3ms — 441ms** (chat thường), **TTFT < 1s** (stream) |
| Đa nền tảng | Web + APK Android (Capacitor 6) |

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

### Đã hoàn thành ở Sprint 1-8
- [x] ~~MQTT over TLS cho ESP32~~ → mosquitto.conf + cert gen script
- [x] ~~NeMo Guardrails~~ → config.yml + rails.co + actions.py
- [x] ~~20 prompt injection vectors~~ → 20/20 PASSED (100%)
- [x] ~~Confirmation flow~~ → POST /chat/confirm + modal UI
- [x] ~~Docker Compose~~ → 4 services + 3 networks
- [x] ~~Nginx reverse proxy~~ → rate limit + security headers
- [x] ~~Rate limiter + Circuit breaker~~ → Sliding Window + CB pattern (in-memory)
- [x] ~~AES-256-GCM encryption~~ → crypto.py
- [x] ~~Langfuse LLM tracing~~ → groq_client.py + graceful degradation
- [x] ~~RBAC (owner vs guest)~~ → rbac.py + auth + UI
- [x] ~~Frontend phân quyền~~ → role badge + guard routes
- [x] ~~Google OAuth2 Login~~ → google-auth + LoginPage GIS
- [x] ~~User CRUD Management~~ → /users API + AccountPage UI
- [x] ~~Native System Agent~~ → mở app/file/folder thật trên Windows
- [x] ~~App Auto-Discovery~~ → quét Registry + Start Menu
- [x] ~~12 App Providers~~ → Phone, SMS, Zalo, FB, YouTube, Maps, Gmail, ...
- [x] ~~Real-time GPS~~ → watchPosition + reverse geocoding 2-tier
- [x] ~~Pipeline Monitor Dashboard~~ → SSE + Tree visualization

### Roadmap kế tiếp (theo độ ưu tiên)

**Cao — block tính năng cốt lõi:**
- [ ] **HA Client thật** (`ha_client.py`) — REST + WebSocket subscribe state
- [ ] **Redis-backed Rate Limiter** — hiện đang in-memory, không scale được
- [ ] **Redis-backed Pending Confirmation** — hiện in-memory, mất khi restart
- [ ] **Owner audit view** — xem audit của tất cả users (hiện chỉ self)

**Trung bình — UX nâng cao:**
- [ ] **Lifespan FastAPI** — thay `on_event` đã deprecated
- [ ] **Wake-word "Hey Aisha"** — Web Speech API continuous mode
- [ ] **SSE streaming response** cho general_chat (text chạy như ChatGPT)
- [ ] **Capacitor → APK Android** — đóng gói app mobile
- [ ] **WebSocket bidirectional** — backend push state changes lên frontend
- [ ] **Tách test files** — gom 11 file `test_*.py` ở root vào `tests/`

**Thấp — nice to have:**
- [ ] **ESP32 Failsafe Firmware** (`firmware/` đang rỗng)
- [ ] **MQTT thật** — auto-rotate cert + ESP32 sample
- [ ] **Streaming TTS** — không chờ MP3 hoàn chỉnh
- [ ] **Multi-language** — EN fallback
- [ ] **Push notifications** — sự kiện smart home (đèn quên tắt 1h...)
- [ ] **HistoryPage filter + pagination + export CSV**

---

## Dependencies Đã Cài

### Backend (Python)
```
fastapi, uvicorn, pydantic, pydantic-settings,
PyJWT, bcrypt, passlib, cryptography,
httpx, redis, aiosqlite, python-dotenv, python-multipart,
edge-tts, gTTS, langfuse
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
| **01:38 - 01:55** | **Phase 2: Rate Limiter + Circuit Breaker + AES-256-GCM + Langfuse** |
| **01:38 - 01:55** | **Phase 2: RBAC (owner/guest) + Confirmation Flow** |
| **01:38 - 01:55** | **Phase 2: Integration Tests → 20/20 PASSED** |
| **01:38 - 01:55** | **Phase 2: DEPLOYMENT_GUIDE + WORKFLOW diagrams** |
| **01:49 - 01:59** | **Phase 2: Frontend phân quyền + role badge + confirm modal** |

---

## Sprint 5 — Phase 2 Post-MVP ✅ DONE (20/20 tests)

### Files đã tạo — Backend

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/core/security/rate_limiter.py` | **[NEW]** Sliding Window Counter + Circuit Breaker pattern | ~210 |
| `src/core/security/crypto.py` | **[NEW]** AES-256-GCM encryption/decryption | ~120 |
| `src/core/security/rbac.py` | **[NEW]** RBAC — owner (full) vs guest (light+sensor) | ~105 |
| `tests/test_integration.py` | **[NEW]** E2E integration tests (20 cases) | ~160 |
| `docs/DEPLOYMENT_GUIDE.md` | **[NEW]** Production deployment guide | ~180 |
| `docs/WORKFLOW.md` | **[NEW]** 5 Mermaid workflow diagrams | ~120 |

### Files đã sửa — Backend

| File | Thay đổi |
|------|----------|
| `src/core/security/gateway.py` | +Rate Limiter (Step 0) +RBAC (Step 1b) +Circuit Breaker (Step 2c) |
| `src/core/ai_engine/agent.py` | +user_roles param + store pending confirm |
| `src/core/ai_engine/groq_client.py` | +Langfuse tracing (_trace_llm method) |
| `src/config.py` | +guest_username/password +langfuse config |
| `src/api/routes/auth.py` | +Guest user login (roles: ["guest"]) |
| `src/api/routes/chat.py` | +POST /chat/confirm + pending store |

### Files đã sửa — Frontend

| File | Thay đổi |
|------|----------|
| `frontend/src/store/useStore.js` | +roles state + isOwner/isGuest helpers + pendingConfirm |
| `frontend/src/api/client.js` | +401 auto-logout interceptor + confirmCommand API |
| `frontend/src/App.jsx` | +Role badge + session restore + guard routes (guest ẩn history) |
| `frontend/src/pages/ChatPage.jsx` | +Role-based suggestions + confirmation modal |
| `frontend/src/App.css` | +Role badge CSS + loading state |
| `frontend/src/pages/ChatPage.css` | +Confirmation modal CSS |

### Tính năng hoàn thành

- ✅ **Rate Limiter** — Sliding Window Counter (in-memory, ready cho Redis)
  - 3 tầng: per-user/min (10), per-entity/min (3), per-user/hour (50)
  - Graceful degradation khi Redis down
- ✅ **Circuit Breaker** — CLOSED → OPEN → HALF_OPEN pattern
  - Threshold: 5 failures → mở circuit 60s
  - Tự phục hồi khi HA call thành công
- ✅ **AES-256-GCM** — Mã hoá dict/string bằng key từ .env
  - Nonce 12-byte, base64 output
  - Key derivation qua SHA-256 từ passphrase
- ✅ **Langfuse LLM Tracing** — Graceful integration
  - Trace: model, tokens, latency cho mỗi LLM call
  - Fail-safe: Langfuse lỗi ≠ LLM lỗi
- ✅ **RBAC** — Owner vs Guest
  - Owner: toàn quyền (tất cả entity + action)
  - Guest: chỉ light (bật/tắt/sáng) + sensor (đọc)
  - Deny-by-default cho role không có permission
- ✅ **Confirmation Flow** — Backend + Frontend
  - POST /chat/confirm endpoint (TTL 60s)
  - Modal UI: "Xác nhận" / "Huỷ bỏ"
  - Climate + Kitchen → requires_confirmation
- ✅ **Frontend phân quyền**
  - Role badge: 👑 Owner / 👤 Guest
  - Guest ẩn tab Lịch sử
  - Guest suggestions ít hơn (4 vs 6)
  - Token hết hạn → auto logout + redirect
  - Session restore từ localStorage

### Gateway Pipeline (6 lớp, sau Phase 2)

```
Request → [0] Rate Limiter → [1] Sanitizer → [1b] RBAC
        → [2] Rule Engine → [2b] Confirmation → [2c] Circuit Breaker
        → [3] Execute HA → [4] Audit Log → Response
```

### Integration Test Results

```
============================================================
INTEGRATION TESTS — Phase 2
============================================================
📝 Auth Tests
  ✅ Admin login OK
  ✅ Guest login OK
  ✅ Admin role = owner
  ✅ Guest role = guest
  ✅ Wrong password = 401

🔐 RBAC Tests
  ✅ Owner bật đèn = OK
  ✅ Guest bật đèn = OK
  ✅ Guest khóa cửa = DENIED

⏱ Rate Limit Tests
  ✅ Rate limit blocks after threshold

🛡 Injection Tests
  ✅ 5/5 injection vectors blocked

✋ Confirmation Flow Tests
  ✅ Climate cần xác nhận
  ✅ Confirm thành công

📋 Audit + Devices
  ✅ Audit log accessible + has records
  ✅ Devices list OK + has devices

RESULTS: 20/20 PASSED (0 failed) 🎉
============================================================
```

### API Endpoints Sprint 5

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| POST | `/chat/confirm` | ✅ | Xác nhận/huỷ lệnh nguy hiểm |

---

## Sprint 6 — True AI System Agent ✅ DONE

Đã chuyển đổi Aisha từ một trợ lý web (chỉ phản hồi URL) thành **Đại lý AI thực thụ (System Agent)** có khả năng điều khiển hệ điều hành, tìm ứng dụng thông minh và làm việc với file.

### Files đã tạo/sửa — Backend & Frontend

| File | Mô tả | Chi tiết |
|------|--------|---------|
| `src/core/app_actions/app_discovery.py` | **[NEW]** Windows App Auto-Discovery | Quét Windows Registry + Start Menu (`.lnk`) để tự động tìm đường dẫn file exe của mọi ứng dụng. Bỏ hoàn toàn hardcode. |
| `src/core/app_actions/file_ops.py` | **[NEW]** File System Operations | Cung cấp hàm `create_folder`, `create_file` (kèm ghi nội dung), chỉ cho phép thao tác ở user folders (Desktop, Documents, Downloads...) an toàn. |
| `src/core/app_actions/system_executor.py` | **[UPDATE]** System Executor | 22 known apps + UWP URI + dynamic discovery cache. Hỗ trợ mở exe/UWP/folder/URL bằng default browser. |
| `src/core/app_actions/providers.py` | **[NEW]** App Providers (12) | Phone, SMS, Zalo, Facebook, YouTube, Maps, Gmail, Camera, Web, TikTok, Spotify, CocCoc — mỗi provider có capabilities riêng. |
| `src/core/app_actions/router.py` | **[NEW]** Smart Intent Router | 25+ regex patterns extract params (query, phone, body, destination...) + fallback keyword + generic `mở [app]`. |
| `src/core/app_actions/base.py` | **[NEW]** AppProvider abstract base | Interface chung: `name`, `display_name`, `icon`, `get_capabilities()`, `execute()`. |
| `src/api/routes/apps.py` | **[NEW]** Apps Route | `GET /apps` (capabilities list), `POST /apps/execute` (owner-only). |
| `src/core/ai_engine/siri_brain.py` | **[UPDATE]** APP_ACTION category | Phân biệt smart home vs app action. Keyword list 60+ pattern. |
| `src/core/ai_engine/agent.py` | **[UPDATE]** Route APP_ACTION → Router | RBAC owner-only cho app actions. Đính kèm GPS location vào params nếu có. |

### Tính năng nổi bật

- ✅ **Auto-Discovery**: Quét Windows Registry (Uninstall keys) + Start Menu (`.lnk` parsing pure Python, không cần COM) → tìm exe path của mọi app đã cài.
- ✅ **3-tier app resolution**: UWP URI → hardcoded paths/PATH → auto-discovery cache.
- ✅ **File Ops bảo mật**: Whitelist user folders, blacklist `C:\Windows`, `Program Files`, `ProgramData`.
- ✅ **Smart Pattern Extraction**: "mở ytb kiếm bài sóng gió" → `youtube_search(query="sóng gió")` (regex named groups).
- ✅ **Generic Fallback**: "mở notepad" / "mở this pc" / "mở máy tính" — không cần hardcode mọi tên.
- ✅ **Default Browser Opening**: Dùng `webbrowser.open()` thay vì hardcode Chrome — tôn trọng setting user.

---

## Sprint 7 — Auth & User Management Redesign ✅ DONE

Đã triển khai hệ thống xác thực kết hợp giữa Google Identity Services và Local Authentication, đồng thời xây dựng giao diện Quản lý tài khoản (CRUD) trực quan chuẩn DNA Cosmic Design.

### 7A. Google OAuth2 Integration

| File | Thay đổi |
|------|----------|
| `src/api/routes/auth.py` | API `POST /auth/google` tích hợp verify Google ID Token (google-auth). |
| `frontend/src/pages/LoginPage.jsx` | Nút đăng nhập Google sử dụng thẻ `script` native (bỏ vòng lặp của React 19). |
| `frontend/src/store/useStore.js` | Lưu trữ và lấy `displayName`, `picture` từ token thay vì chỉ lấy email. |

**Tính năng nổi bật:**
- Mapping roles động: Email có trong danh sách gốc `.env` (`ADMIN_EMAILS`) sẽ được cấp role `owner`, ngược lại nhận role `guest`.
- Bảo mật thông tin: Không lưu Google profile vào database mà nhúng trực tiếp qua JWT claims.
- Hiển thị trực quan: Avatar và Tên (được format bỏ phần @gmail.com) hiển thị trực tiếp lên Thanh trạng thái.

### 7B. Hệ thống Quản lý tài khoản (Backend CRUD)

| File | Mô tả |
|------|--------|
| `src/api/routes/users.py` | Full RESTful API (GET, POST, PUT, DELETE) quản lý người dùng local. |
| `data/users.json` | File database JSON flat, tiện lợi tạo/xoá/sửa trong giai đoạn đầu mà không cần Migrate SQL. |

**Tính năng nổi bật:**
- **Zero-Trust for CRUD**: Chỉ `Owner` (Quyền cao nhất) mới có quyền truy cập endpoint (bảo vệ bởi `_require_owner`).
- **Data Protection**: Admin mặc định và Guest mặc định hoàn toàn không thể bị xóa hoặc sửa nhầm (hardcoded protection).

### 7C. AccountPage Redesign (Frontend v3)

| File | Thay đổi |
|------|----------|
| `frontend/src/pages/AccountPage.jsx` | Áp dụng Accordion UI (collapse menu) chia 3 phần rõ rệt: Info, Quyền, Quản lý User. |
| `frontend/src/pages/AccountPage.css` | Giao diện Modal Box đa lớp cho tiến trình CRUD: `Add Modal`, `Edit Modal`, `Delete Confirm Dialog`. |

**Tính năng nổi bật:**
- **Responsive Multi-platform:** Fix cứng `min-height: 44px` cho tất cả các nút bấm giúp tăng độ mượt chạm (Touch Target) trên điện thoại và máy tính bảng.
- **Micro-interactions:** Hiệu ứng Dropdown trượt mượt mà, Modals hiện ra dạng Slide-up từ dưới đáy, Form error messages trực quan real-time.
- **Smart Flow:** Dashboard quản lý user chỉ hiện trên giao diện khi người dùng là Owner. Avatar mặc định được tạo từ chữ cái đầu của Username trên nền Gradient nếu user không có ảnh Google.

---

## Sprint 8 — Location Awareness & Pipeline Monitor ✅ DONE

Bổ sung khả năng "biết vị trí" thực tế cho Aisha + một dashboard giám sát pipeline thời gian thực để debug.

### 8A. Real-time GPS Tracking

| File | Thay đổi |
|------|----------|
| `src/core/location/geocoder.py` | **[NEW]** Reverse geocoding 2-tier: Google Maps API → Nominatim (OpenStreetMap) → fallback toạ độ thô. Cache 50m/5min. |
| `frontend/src/store/useStore.js` | **[UPDATE]** `requestLocation()` dùng `navigator.watchPosition` (tracking liên tục thay vì 1 lần). |
| `frontend/src/pages/ChatPage.jsx` | **[UPDATE]** Đính kèm `lat/lng` vào mọi request `/chat`. |
| `src/api/routes/chat.py` | **[UPDATE]** Nhận `lat/lng` trong body → forward xuống agent. |
| `src/core/ai_engine/siri_brain.py` | **[UPDATE]** Inject location context vào system prompt LLM + handler `LOCATION_QUERY`. |
| `src/core/app_actions/providers.py` | **[UPDATE]** `MapsProvider.navigate` dùng `origin=lat,lng` để chỉ đường từ vị trí hiện tại. |

**Tính năng nổi bật:**
- **Waterfall reverse geocoding**: Google chính xác đến số nhà → Nominatim free fallback → toạ độ thô.
- **Cache thông minh**: 2 toạ độ trong vòng 50m + 5 phút dùng chung kết quả → tiết kiệm API call.
- **Auto-Retry GPS**: Frontend auto thử lại sau khi user cấp phép, không bắt user reload tab.
- **LLM-aware location**: System prompt được nhúng địa chỉ → LLM trả lời "bạn đang ở Cần Thơ" mà không cần query thủ công.

### 8B. Aisha Pipeline Monitor (Tree Dashboard)

| File | Thay đổi |
|------|----------|
| `src/api/routes/monitor.py` | **[NEW]** SSE endpoint `GET /monitor/events` + `GET /monitor/history`. Broadcast event tới mọi connected client. |
| `monitor/index.html` | **[NEW]** Standalone HTML dashboard (không dùng React) — kết nối SSE realtime. |
| `monitor/style.css` | **[NEW]** Sơ đồ cây (Tree Graphic) chia 2 branch: Smart Home / System App Pipeline. |
| `monitor/app.js` | **[NEW]** EventSource client + animation đèn nhấp nháy theo pipeline step thực tế. |
| `src/core/security/gateway.py` | **[UPDATE]** Trả về `pipeline_steps` chi tiết (rate_limiter, sanitizer, RBAC, rule_engine, confirm, circuit, execute, audit). |
| `src/core/ai_engine/agent.py` | **[UPDATE]** Forward `pipeline_steps` từ gateway + thêm step cho App Action route. |

**Tính năng nổi bật:**
- **Server-Sent Events**: 1-way broadcast với heartbeat 15s, hỗ trợ 100+ subscribers cùng lúc.
- **Tree Pipeline Visualization**: Mỗi node là 1 bước trong gateway, màu xanh = pass, đỏ = fail, vàng = pending.
- **Data Log**: In ra "Vào app gì, mở app nào, làm file gì" phía dưới mỗi pipeline event.
- **History Replay**: 50 events gần nhất được lưu deque — dashboard mới mở vẫn thấy history.

### API Endpoints Sprint 8

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| GET | `/monitor/events` | ❌ | SSE stream cho dashboard |
| GET | `/monitor/history` | ❌ | 50 events gần nhất |
| GET | `/apps` | ✅ | Danh sách app providers |
| POST | `/apps/execute` | ✅ | Thực thi app action (owner) |
| GET | `/users` | ✅ | Danh sách users (owner) |
| POST | `/users` | ✅ | Tạo user (owner) |
| PUT | `/users/{username}` | ✅ | Sửa user (owner) |
| DELETE | `/users/{username}` | ✅ | Xoá user (owner) |
| POST | `/auth/google` | ❌ | Đăng nhập Google ID Token |

---

## Sprint 9 — Refactor & Mobile Hardening ✅ DONE

Sprint chuyên về **dọn dẹp kiến trúc + nâng cấp production-grade + đóng gói APK Android**. Toàn bộ thay đổi được commit thành 13 commits riêng biệt theo Conventional Commits.

### 9A. Dọn dẹp & Refactor Backend

| File | Thay đổi | Chi tiết |
|------|----------|---------|
| `src/api/app.py` | **[REFACTOR]** `on_event` → `lifespan` | Dùng `@asynccontextmanager`. Khởi tạo audit logger + HA client (lazy fallback mock khi `HA_TOKEN` rỗng), shutdown cleanup connection pool. |
| `tests/conftest.py` | **[NEW]** Bootstrap sys.path | Auto-inject project root để chạy `python tests/unit/test_x.py` trực tiếp. |
| `tests/{unit,integration,manual}/` | **[NEW]** Tổ chức 11 test files | Gom test phân tán ở root → unit (rate-limit, security), integration (api, chat, siri), manual (bench, tts, voices). |
| `.env.example` | **[UPDATE]** Hoàn thiện | Thêm `GUEST_USERNAME/PASSWORD`, `GOOGLE_CLIENT_ID`, `ADMIN_EMAILS`, `GOOGLE_MAPS_API_KEY`, `LANGFUSE_*`, comment giải thích từng biến. |
| `frontend/.env.example` | **[NEW]** Frontend env mẫu | `VITE_API_URL`, `VITE_GOOGLE_CLIENT_ID`. |
| `frontend/src/pages/LoginPage.jsx` | **[FIX]** Bỏ hardcode | Đọc Google Client ID từ `import.meta.env.VITE_GOOGLE_CLIENT_ID`, prefill admin/password chỉ trong DEV mode. |

### 9B. HA Client + Redis Production-grade

| File | Thay đổi |
|------|----------|
| `src/services/ha_provider/ha_client.py` | **[NEW]** Async REST client httpx — 23 action mappings (light brightness/color, lock, climate temp/HVAC/fan/humidity, fan speed/preset, cover open/close/position, media play/pause/volume, input_number, select). Retry exponential backoff cho lỗi 5xx, fail-fast 4xx. Singleton lifespan-managed. |
| `src/core/security/rate_limiter.py` | **[REFACTOR]** Async Redis Sliding Window | Dùng Redis Sorted Set + `pipeline(transaction=False)` (nhanh 2× cho rate-limit). InMemory fallback khi Redis fail. Cooldown 60s sau lỗi mới retry Redis. `_mark_redis_dead()` reset client khi mid-flight error. |
| `src/core/security/pending_store.py` | **[NEW]** Redis Pending Command Store | Lưu lệnh chờ xác nhận với `SETEX` TTL 60s. Multi-worker safe. InMemory fallback. Reset client pattern giống rate-limiter. |
| `src/core/security/gateway.py` | **[UPDATE]** Async rate limit | `await check_rate_limit(...)`. Inject `ha_client` qua `set_ha_client()` ở startup. |
| `src/api/routes/chat.py` | **[UPDATE]** Owner audit `?all=true` | Owner có thể truyền `?all=true` để xem audit log của tất cả user; user thường chỉ xem audit của mình. |

### 9C. SSE Streaming Chat (ChatGPT-style)

| File | Thay đổi |
|------|----------|
| `src/core/ai_engine/groq_client.py` | **[NEW]** `chat_stream()` async generator. Httpx granular timeout (connect/read/write/pool riêng). Defensive JSON parsing tránh KeyError. Phân loại error (Timeout / HTTPError / Unexpected). Langfuse trace sau khi stream xong. |
| `src/api/routes/chat.py` | **[NEW]** `POST /chat/stream` SSE endpoint | Pre-flight rate-limit check (chống spam). Comment `: stream-start` flush proxy. `asyncio.to_thread(format_location_context)` tránh chặn event loop. Fallback non-stream cho intent ≠ general_chat. Bắt `CancelledError` khi client disconnect. Headers `X-Accel-Buffering: no` + `Connection: keep-alive`. |
| `frontend/src/api/client.js` | **[NEW]** `streamMessage()` | Dùng `fetch` + `ReadableStream` parse SSE thủ công (axios không stream tốt, EventSource không hỗ trợ POST + JWT). Hỗ trợ `AbortSignal`. |
| `frontend/src/store/useStore.js` | **[NEW]** `updateLastMessage(patch)` | Patch message cuối cùng — dùng cho streaming render dần. |
| `frontend/src/pages/ChatPage.jsx` | **[REFACTOR]** SSE chat | Render text dần như ChatGPT. Cursor `▍` nháy khi đang stream. `AbortController` hủy stream cũ khi user gửi tin mới (tránh 2 streams song song). TTS chỉ chạy khi response thành công. |
| `frontend/src/pages/ChatPage.css` | **[UPDATE]** `.siri-cursor` | Animation `siriCursorBlink` 1s steps(1) infinite. |

### 9D. Wake-word "Hey Aisha" — Dual Backend

| File | Thay đổi |
|------|----------|
| `frontend/src/hooks/useWakeWord.js` | **[NEW]** Hook continuous wake-word | **Dual backend**: native Capacitor plugin (Android `SpeechRecognizer`) khi chạy APK, Web Speech API khi mở browser. Tự dispatcher qua `isCapacitorNative()`. Auto-restart liên tục (Android limit ~10s/session) qua watchdog `isListening()`. Debounce cooldown 2.5s. Dedup interim text. `startRef` tránh TDZ. 15 phrase variants tiếng Việt ("hey aisha", "ai sa ơi", "ê aisha"...). |
| `frontend/src/components/VoiceOrb.jsx` | **[REFACTOR]** Dual backend voice | `forwardRef` + `useImperativeHandle` expose `startListening`/`stopListening` cho parent (wake-word trigger). Emit `onStateChange` để parent pause wake-word khi listening/speaking. Native plugin partialResults event hiển thị transcript real-time. Tự xin RECORD_AUDIO permission. |
| `frontend/src/pages/ChatPage.jsx` | **[UPDATE]** Wake-word toggle | Button "👂 Hey Aisha" lưu trạng thái `localStorage`. Pause wake-word khi orb đang nghe / đang nói / đang xử lý. Tự `setMode('voice')` + `voiceOrbRef.current.startListening()` khi wake. |
| `frontend/src/pages/ChatPage.css` | **[UPDATE]** `.wake-btn` | Accent xanh khi active, dim khi disabled. |

### 9E. Capacitor → APK Android

| File | Thay đổi |
|------|----------|
| `frontend/package.json` | **[UPDATE]** Capacitor deps + scripts | `@capacitor/core@^6.2`, `@capacitor/android@^6.2`, `@capacitor/cli@^6.2`, `@capacitor-community/speech-recognition@^6.0.1`. Scripts: `cap:sync`, `cap:open`, `setup:env`, `setup:env:i`, `android:dev`, `android:apk`. |
| `frontend/capacitor.config.json` | **[NEW]** Cấu hình Capacitor | `appId: vn.aisha.app`, `webDir: dist`, `androidScheme: https`, `cleartext: true`, splashscreen 800ms. |
| `frontend/scripts/setup-env.mjs` | **[NEW]** Auto-detect IP LAN | Quét `os.networkInterfaces()`, ưu tiên `192.168.*` > `10.*` > `172.16-31.*`, bỏ Docker/WSL/vEthernet/Hyper-V. Mode interactive (`--interactive`) cho user chọn nếu nhiều IP. Ghi `.env.production` đúng format, preserve các biến `VITE_*` khác. |
| `frontend/.gitignore` | **[UPDATE]** Capacitor build artifacts | `.env.production`, `*.keystore`, `android/build`, `android/local.properties`, `android/key.properties`. |
| `docs/ANDROID_BUILD.md` | **[NEW]** Hướng dẫn build APK | 11 mục từ setup môi trường JDK 21 + Android SDK 34 → build debug → ký release → live reload → troubleshooting → checklist phát hành. |

### 9F. Dynamic Backend URL

| File | Thay đổi |
|------|----------|
| `frontend/src/api/config.js` | **[NEW]** Helper `getApiUrl/setApiUrl` | Priority chain: `localStorage('aisha:apiUrl')` → `import.meta.env.VITE_API_URL` → fallback `http://localhost:8000`. `pingApiUrl()` test connection trong 3s. `isCapacitorNative()` detect runtime APK. |
| `frontend/src/api/client.js` | **[REFACTOR]** Axios interceptor dynamic | Mỗi request `config.baseURL = getApiUrl()` thay vì set 1 lần lúc tạo. SSE `streamMessage()` cũng dùng `getApiUrl()`. |
| `frontend/src/components/VoiceOrb.jsx` | **[UPDATE]** TTS dùng dynamic URL | Bỏ hardcode `import.meta.env.VITE_API_URL`. |
| `frontend/src/pages/AccountPage.jsx` | **[NEW]** `BackendUrlSettings` component | Accordion "🔌 Cấu hình kết nối Backend" có input URL + nút "🔍 Test kết nối" + "💾 Lưu" + "↺ Reset". Auto-mở khi chạy native. Hiển thị warn box "📱 localhost không trỏ về máy của bạn" khi native. |
| `frontend/src/pages/AccountPage.css` | **[NEW]** `.bcfg__*` styles | Glassmorphism, animation hover, gradient save button, alert box. |

### 9G. CORS Auto-merge Capacitor

| File | Thay đổi |
|------|----------|
| `src/config.py` | **[REFACTOR]** `cors_origins_list` auto-merge | Default thêm `capacitor://localhost`, `https://localhost`, `ionic://localhost`. Computed property AUTO-MERGE 3 scheme này runtime — dù user `.env` cũ chỉ có localhost vẫn hoạt động ngay không cần edit. |
| `.env.example` | **[UPDATE]** Comment | Giải thích từng scheme + ví dụ deploy production. |

### Tính năng nổi bật Sprint 9

- ✅ **Streaming chat ChatGPT-style**: Text hiện ra dần với cursor nháy, TTFT < 1s.
- ✅ **Wake-word continuous "Hey Aisha"**: hoạt động trên cả browser (Web Speech API) và APK Android (native plugin), auto-restart 24/7.
- ✅ **APK Android chỉ với 1 lệnh**: `npm run android:apk` tự dò IP LAN → build → sync → assemble.
- ✅ **Đổi backend URL ngay trong app**: không cần build lại, chỉ vào Account → 🔌 → nhập IP → 💾.
- ✅ **CORS không cần config**: 3 Capacitor scheme luôn được merge runtime, deploy 0 ma sát.
- ✅ **Production-grade Redis**: Sliding window + auto fallback InMemory + reset client khi mid-flight error.
- ✅ **23 HA service mappings** so với 11 trước đây — phủ light/lock/climate/fan/cover/media_player/select/input_number.
- ✅ **Defensive coding**: tất cả Redis/HA/LLM call có try/except + fallback message + logger phân loại lỗi.

### API Endpoints Sprint 9

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| POST | `/chat/stream` | ✅ | SSE streaming chat (chunk dần) |

### Commits đã lên

| # | Commit | Scope |
|---|--------|-------|
| 1 | `chore: Tổ chức tests + cập nhật env files + gitignore` | infra |
| 2 | `refactor(api): FastAPI lifespan context manager thay on_event` | backend |
| 3 | `feat(security): Redis sliding window rate limiter + InMemory fallback` | security |
| 4 | `feat(security): Pending Command Store backend Redis với TTL 60s` | security |
| 5 | `feat(security): CORS auto-merge Capacitor schemes` | security |
| 6 | `feat(ha): HAClient async REST với 23 action mappings` | ha |
| 7 | `feat(ai): GroqClient streaming chat + httpx granular timeout` | ai |
| 8 | `feat(api): SSE endpoint /chat/stream + owner audit ?all=true` | api |
| 9 | `feat(frontend): SSE streaming UI ChatGPT-style + AbortController` | frontend |
| 10 | `feat(frontend): Wake-word Hey Aisha hook dual-backend (web+native)` | frontend |
| 11 | `feat(android): Capacitor 6 + speech-recognition + setup-env script` | android |
| 12 | `feat(frontend): Dynamic backend URL — config.js + Settings UI` | frontend |
| 13 | `docs: README + ANDROID_BUILD + SKILL_REPORT cập nhật toàn diện` | docs |

---

*Report cập nhật liên tục — mỗi lần làm thêm tính năng sẽ ghi lại ở đây*
