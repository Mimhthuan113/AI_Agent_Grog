# 🛠️ Skill Report — Những Gì Đã Làm Được

> **Ngày:** 2026-04-22  
> **Session:** Sprint 1 + Sprint 2 + Sprint 3 (một phần)  
> **Thời gian làm việc:** ~1 giờ

---

## Tổng Quan

Trong session này, đã xây dựng **backend hoàn chỉnh** cho dự án Smart AI Home Hub — từ scaffold đến API endpoint có thể gọi được, bao gồm hệ thống bảo mật 4 lớp và tích hợp AI (Groq LLM).

### Thống kê

| Metric | Giá trị |
|--------|---------|
| Files tạo mới | **24 files** |
| Tổng dòng code | **~2,000 lines** |
| Tests viết | **26 test cases** |
| Tests passed | **26/26 (100%)** |
| Sprints hoàn thành | 2.5 / 6 |
| API endpoints | 7 endpoints |

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

## Sprint 3 — AI Engine & Chat API (IN PROGRESS)

### Files đã tạo

| File | Mô tả | Lines |
|------|--------|:-----:|
| `src/core/ai_engine/groq_client.py` | Groq API client + exponential backoff retry | ~160 |
| `src/core/ai_engine/intent_parser.py` | Tiếng Việt → JSON command (LLM + fallback regex) | ~170 |
| `src/core/ai_engine/agent.py` | AI orchestrator — kết nối parser với gateway | ~160 |
| `src/services/ha_provider/entity_registry.py` | 20+ alias tiếng Việt → HA entity_id | ~170 |
| `src/api/routes/chat.py` | `POST /chat`, `GET /devices`, `GET /audit` | ~120 |

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

### API Endpoints Sprint 3

| Method | Path | Auth | Mô tả |
|--------|------|:----:|-------|
| POST | `/chat` | ✅ | Gửi lệnh tiếng Việt |
| GET | `/devices` | ✅ | Danh sách thiết bị |
| GET | `/audit` | ✅ | Lịch sử lệnh |

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

### Sprint 4 — HA Integration
- [ ] `ha_client.py` — kết nối Home Assistant thật
- [ ] NeMo Guardrails config

### Sprint 5 — Testing
- [ ] 20 prompt injection vectors
- [ ] Full integration test suite

### Sprint 6 — Hardening
- [ ] Rate limiter + Circuit breaker
- [ ] AES-256-GCM encryption
- [ ] Langfuse LLM tracing
- [ ] Frontend (React + Capacitor → APK)
- [ ] DEPLOYMENT_GUIDE.md

---

## Dependencies Đã Cài

```
fastapi, uvicorn, pydantic, pydantic-settings,
PyJWT, bcrypt, passlib, cryptography,
httpx, redis, aiosqlite, python-dotenv, python-multipart
```

---

*Report được tạo tự động từ session dev ngày 2026-04-21/22*
