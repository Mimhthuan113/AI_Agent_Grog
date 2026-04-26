"""
Pending Command Store — Redis-backed với InMemory fallback
=============================================================
Lưu các lệnh đang chờ xác nhận (climate, lock, ...). TTL 60s.

Tại sao cần Redis:
- Trước đây dict in-memory → mất hết khi restart server
- Multi-worker (gunicorn -w 4) → mỗi worker có dict riêng → confirm sẽ fail

Pattern:
- Key: `pending:{request_id}` → JSON {command, user_id, created_at}
- TTL: 60s (Redis tự xoá)
- Fallback: dict + cleanup thủ công
"""
from __future__ import annotations

import json
import time
import logging
import asyncio
from typing import Any

logger = logging.getLogger(__name__)


_PENDING_TTL = 60  # 60 giây timeout


class _InMemoryStore:
    """Dict-based fallback. Single-process only."""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def set(self, request_id: str, payload: dict, ttl: int) -> None:
        async with self._lock:
            self._data[request_id] = {**payload, "_expires_at": time.time() + ttl}
            # Cleanup các key đã expire (lazy)
            now = time.time()
            expired = [k for k, v in self._data.items() if v["_expires_at"] < now]
            for k in expired:
                del self._data[k]

    async def get(self, request_id: str) -> dict | None:
        async with self._lock:
            entry = self._data.get(request_id)
            if entry is None:
                return None
            if entry["_expires_at"] < time.time():
                del self._data[request_id]
                return None
            return {k: v for k, v in entry.items() if k != "_expires_at"}

    async def delete(self, request_id: str) -> None:
        async with self._lock:
            self._data.pop(request_id, None)


class PendingCommandStore:
    """
    Store chính — ưu tiên Redis, fallback InMemory.
    Lazy-init Redis ở lần gọi đầu.
    """

    _REDIS_RETRY_SEC = 60.0

    def __init__(self):
        self._memory = _InMemoryStore()
        self._redis = None
        self._redis_failed_at: float = 0.0

    async def _get_redis(self):
        """Lazy-init Redis. Return None nếu fail."""
        if self._redis_failed_at and (time.time() - self._redis_failed_at) < self._REDIS_RETRY_SEC:
            return None
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as aioredis
            from src.config import get_settings
            client = aioredis.from_url(
                get_settings().redis_url,
                decode_responses=True,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
            )
            await client.ping()
            self._redis = client
            self._redis_failed_at = 0.0
            logger.info("[PENDING] Redis backend connected")
            return client
        except Exception as e:
            self._redis_failed_at = time.time()
            logger.warning("[PENDING] Redis unavailable → InMemory: %s", str(e)[:100])
            return None

    def _mark_redis_dead(self) -> None:
        """Đánh dấu Redis chết tạm thời → reset client + cooldown 60s."""
        self._redis_failed_at = time.time()
        self._redis = None

    async def store(self, request_id: str, command: dict, user_id: str) -> None:
        """Lưu lệnh chờ xác nhận."""
        payload = {
            "command": command,
            "user_id": user_id,
            "created_at": time.time(),
        }
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.setex(
                    f"pending:{request_id}",
                    _PENDING_TTL,
                    json.dumps(payload),
                )
                return
            except Exception as e:
                logger.warning("[PENDING] Redis store error → memory: %s", str(e)[:100])
                self._mark_redis_dead()

        await self._memory.set(request_id, payload, _PENDING_TTL)

    async def get(self, request_id: str) -> dict | None:
        """Lấy lệnh đang chờ. Return None nếu không có hoặc đã expire."""
        redis = await self._get_redis()
        if redis is not None:
            try:
                raw = await redis.get(f"pending:{request_id}")
                if raw:
                    return json.loads(raw)
                return None
            except Exception as e:
                logger.warning("[PENDING] Redis get error → memory: %s", str(e)[:100])
                self._mark_redis_dead()

        return await self._memory.get(request_id)

    async def delete(self, request_id: str) -> None:
        """Xoá lệnh khỏi store."""
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.delete(f"pending:{request_id}")
                return
            except Exception as e:
                logger.warning("[PENDING] Redis delete error → memory: %s", str(e)[:100])
                self._mark_redis_dead()

        await self._memory.delete(request_id)


# ── Singleton ─────────────────────────────────────────────

_store: PendingCommandStore | None = None


def get_pending_store() -> PendingCommandStore:
    """Trả về singleton PendingCommandStore."""
    global _store
    if _store is None:
        _store = PendingCommandStore()
    return _store
