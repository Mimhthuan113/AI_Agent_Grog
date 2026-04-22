# ============================================================
# Smart AI Home Hub — Backend Dockerfile
# ============================================================
# Multi-stage build: install deps → copy code → run
# ============================================================

FROM python:3.11-slim AS base

# Security: non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Install system deps (curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# ── Dependencies ─────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application ──────────────────────────────────
FROM deps AS app

# Copy source code
COPY src/ ./src/
COPY static/ ./static/

# Security: no .env or keys in image (mount at runtime)
# Ensure data directory exists
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Switch to non-root
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "src.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
