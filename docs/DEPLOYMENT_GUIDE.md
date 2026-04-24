# 🚀 Deployment Guide — Smart AI Home Hub (Aisha)

> Hướng dẫn deploy hệ thống lên production server.

---

## 1. Yêu Cầu Hệ Thống

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 10 GB | 20 GB |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 |
| Docker | 24.0+ | Latest |
| Docker Compose | v2.20+ | Latest |

---

## 2. Clone & Setup

```bash
# Clone repository
git clone https://github.com/your-org/LyMinhThuan_AI_Agent.git
cd LyMinhThuan_AI_Agent

# Tạo file .env từ template
cp .env.example .env
```

---

## 3. Cấu Hình Environment (.env)

### Bắt buộc thay đổi (⚠️ CRITICAL)

```env
# ── APP ────────────────────────────────────
APP_ENV=production
APP_DEBUG=False

# ── GROQ API (LLM) ────────────────────────
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL_DEFAULT=llama-3.1-8b-instant

# ── ADMIN ACCOUNT (ĐỔI PASSWORD!) ─────────
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_super_strong_password_here

# ── GUEST ACCOUNT ─────────────────────────
GUEST_USERNAME=guest
GUEST_PASSWORD=your_guest_password_here

# ── ENCRYPTION ────────────────────────────
DB_ENCRYPTION_KEY=your_random_32_char_passphrase

# ── REDIS ─────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# ── CORS (domain production) ──────────────
CORS_ORIGINS=https://your-domain.com
ALLOW_PLAIN_HTTP=False
```

### Optional (Langfuse monitoring)

```env
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 4. Tạo JWT Keys

```bash
python infrastructure/scripts/gen_jwt_keys.py
```

Kiểm tra:
```bash
ls keys/
# private.pem  public.pem
```

---

## 5. Build & Run (Docker Compose)

```bash
# Build tất cả services
docker compose build

# Chạy background
docker compose up -d

# Kiểm tra status
docker compose ps

# Xem logs
docker compose logs -f app
```

### Services

| Service | Port | Mô tả |
|---------|------|--------|
| `app` | 8000 | FastAPI backend |
| `redis` | 6379 | Rate limiting + token blacklist |
| `mosquitto` | 8883 | MQTT TLS broker |
| `nginx` | 80/443 | Reverse proxy + rate limit |

---

## 6. Frontend Build

```bash
cd frontend

# Cấu hình API URL cho production
echo "VITE_API_URL=https://your-domain.com" > .env.production

# Build production bundle
npm install
npm run build

# Output trong frontend/dist/
```

Copy `dist/` vào Nginx static files hoặc serve bằng CDN.

---

## 7. Checklist Bảo Mật

### Trước khi deploy

- [ ] Đổi `ADMIN_PASSWORD` (không dùng default)
- [ ] Đổi `GUEST_PASSWORD`
- [ ] Đổi `REDIS_PASSWORD`
- [ ] Set `DB_ENCRYPTION_KEY` (32+ ký tự random)
- [ ] Set `APP_ENV=production`
- [ ] Set `APP_DEBUG=False`
- [ ] Set `ALLOW_PLAIN_HTTP=False`
- [ ] Cấu hình `CORS_ORIGINS` đúng domain

### SSL/TLS

- [ ] Cài Let's Encrypt cert cho Nginx
- [ ] MQTT broker dùng TLS certs (`infrastructure/mosquitto/certs/`)

### Sau khi deploy

- [ ] Test `GET /health` → 200
- [ ] Test login với credentials mới
- [ ] Test injection vectors → tất cả bị chặn
- [ ] Kiểm tra audit log (`GET /audit`)

---

## 8. Monitoring

### Langfuse (LLM Tracing)

Nếu cấu hình `LANGFUSE_*` env vars:
- Truy cập [Langfuse Dashboard](https://cloud.langfuse.com)
- Xem traces: model, tokens, latency cho mỗi LLM call
- Phát hiện slow queries, high token usage

### Application Logs

```bash
# Realtime logs
docker compose logs -f app

# Chỉ xem errors
docker compose logs app | grep ERROR
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok", "timestamp": "..."}
```

---

## 9. Backup

### Audit Database

```bash
# Backup audit.db
docker compose exec app cp /app/data/audit.db /app/data/audit_backup_$(date +%Y%m%d).db

# Hoặc copy ra host
docker cp $(docker compose ps -q app):/app/data/audit.db ./backup/
```

### JWT Keys

```bash
cp keys/private.pem backup/
cp keys/public.pem backup/
```

---

## 10. Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Redis connection refused | Redis chưa start | `docker compose up -d redis` |
| JWT decode error | Keys không match | Tạo lại keys + restart |
| 429 Too Many Requests | Rate limit | Tăng `RATE_LIMIT_PER_USER_PER_MINUTE` |
| TTS timeout | DNS/firewall | Kiểm tra kết nối internet |
| Groq API error | API key sai/hết quota | Kiểm tra `GROQ_API_KEY` |

---

## 11. Cập Nhật

```bash
# Pull code mới
git pull origin main

# Rebuild + restart
docker compose build app
docker compose up -d app

# Kiểm tra health
curl http://localhost:8000/health
```

---

*Tài liệu này cập nhật theo phiên bản mới nhất của codebase.*
