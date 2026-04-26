"""
Rate Limiter + Circuit Breaker — Redis-based với InMemory fallback
=================================================================
Bảo vệ hệ thống khỏi lạm dụng và cascading failure.

Rate Limiter:
  - Async Sliding Window Counter (Redis Sorted Set)
  - Tự động fallback InMemory nếu Redis không sẵn sàng
  - 3 tầng: per-user/min, per-entity/min, per-user/hour

Circuit Breaker:
  - Đếm failed HA calls
  - Nếu > threshold → mở circuit (reject ngay, không gọi HA)
  - Tự đóng sau timeout (60s mặc định)

Redis sliding window pattern (mu lua-free, dung pipeline):
  ZADD key {ts}-{rand} {ts}        → thêm request hiện tại
  ZREMRANGEBYSCORE key 0 (now-window) → dọn entries cũ
  ZCARD key                         → đếm count
  EXPIRE key window+1               → auto cleanup

Nếu count > limit → ZREMRANGEBYRANK key -1 -1 (bỏ để fair counting).
"""

from __future__ import annotations

import os
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ── Rate Limit Result ──────────────────────────────────────

class RateLimitResult(str, Enum):
    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class RateLimitInfo:
    result: RateLimitResult
    remaining: int = 0           # Số request còn lại
    reset_at: float = 0.0       # Timestamp khi reset
    reason: str = ""


# ── In-Memory Fallback (khi Redis down) ─────────────────
class InMemoryRateLimiter:
    """
    Fallback rate limiter khi Redis không khả dụng.
    Dùng dict + sliding window đơn giản. Thread-safe với asyncio.Lock.
    """

    def __init__(self):
        self._windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_sec: int) -> RateLimitInfo:
        async with self._lock:
            now = time.time()
            cutoff = now - window_sec

            if key not in self._windows:
                self._windows[key] = []

            # Xoá entries cũ
            self._windows[key] = [t for t in self._windows[key] if t > cutoff]

            if len(self._windows[key]) >= limit:
                return RateLimitInfo(
                    result=RateLimitResult.RATE_LIMITED,
                    remaining=0,
                    reset_at=self._windows[key][0] + window_sec,
                    reason=f"Vượt quá {limit} requests trong {window_sec}s",
                )

            self._windows[key].append(now)
            return RateLimitInfo(
                result=RateLimitResult.ALLOWED,
                remaining=limit - len(self._windows[key]),
            )

    def cleanup(self):
        """Dọn dẹp entries cũ (gọi định kỳ)."""
        now = time.time()
        cutoff = now - 3600  # Giữ tối đa 1 giờ
        for key in list(self._windows.keys()):
            self._windows[key] = [t for t in self._windows[key] if t > cutoff]
            if not self._windows[key]:
                del self._windows[key]


# ── Redis Sliding Window Limiter ─────────────────────
class RedisRateLimiter:
    """
    Sliding window rate limiter dùng Redis Sorted Set.
    An toàn cho multi-worker, multi-process.
    """

    def __init__(self, redis_client):
        self._redis = redis_client

    async def check(self, key: str, limit: int, window_sec: int) -> RateLimitInfo:
        """
        Check + record trong 1 pipeline (giảm round-trip).
        Race condition: tối đa 1 request dư thay vì chặn → chấp nhận cho production.
        """
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - window_sec * 1000
        member = f"{now_ms}-{uuid.uuid4().hex[:8]}"

        try:
            # transaction=False → không bao MULTI/EXEC, nhanh hơn cho rate-limit
            # (chấp nhận race-condition nhỏ giữa zcard và zadd).
            pipe = self._redis.pipeline(transaction=False)
            pipe.zremrangebyscore(key, 0, cutoff_ms)
            pipe.zadd(key, {member: now_ms})
            pipe.zcard(key)
            pipe.expire(key, window_sec + 1)
            results = await pipe.execute()
            count = int(results[2])
        except Exception as e:
            logger.warning("[RATE:Redis] error: %s → fallback memory", str(e)[:100])
            raise  # Caller sẽ fallback

        if count > limit:
            # Bỏ request vừa thêm để fair counting
            try:
                await self._redis.zrem(key, member)
            except Exception:
                pass
            return RateLimitInfo(
                result=RateLimitResult.RATE_LIMITED,
                remaining=0,
                reset_at=time.time() + window_sec,
                reason=f"Vượt quá {limit} requests trong {window_sec}s",
            )

        return RateLimitInfo(
            result=RateLimitResult.ALLOWED,
            remaining=max(0, limit - count),
        )


# ── Circuit Breaker ────────────────────────────────────────

class CircuitState(str, Enum):
    CLOSED = "closed"       # Bình thường — cho phép request
    OPEN = "open"           # Đang mở — reject tất cả
    HALF_OPEN = "half_open" # Thử 1 request, nếu OK → đóng


class CircuitBreaker:
    """
    Circuit Breaker pattern — bảo vệ HA service.

    CLOSED → lỗi liên tiếp > threshold → OPEN
    OPEN → sau timeout → HALF_OPEN
    HALF_OPEN → 1 request OK → CLOSED | fail → OPEN
    """

    def __init__(self, threshold: int = 5, timeout_sec: int = 60):
        self._threshold = threshold
        self._timeout_sec = timeout_sec
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Kiểm tra timeout → chuyển sang HALF_OPEN
            if time.time() - self._last_failure_time >= self._timeout_sec:
                self._state = CircuitState.HALF_OPEN
                logger.info("[CIRCUIT] State: OPEN → HALF_OPEN (timeout expired)")
        return self._state

    def allow_request(self) -> bool:
        """Kiểm tra có cho phép request không."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # Cho thử 1 request
        return False  # OPEN → reject

    def record_success(self):
        """Ghi nhận HA call thành công."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("[CIRCUIT] State: HALF_OPEN → CLOSED (success)")
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self):
        """Ghi nhận HA call thất bại."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "[CIRCUIT] State: → OPEN (failures=%d, threshold=%d)",
                self._failure_count, self._threshold,
            )

    def get_info(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "threshold": self._threshold,
            "timeout_sec": self._timeout_sec,
        }


# ── Main Rate Limiter ─────────────────────────
class RateLimiter:
    """
    Rate Limiter chính — ưu tiên Redis, fallback InMemory khi Redis không sẵn sàng.

    Redis client được lazy-init ở lần gọi đầu tiên.
    """

    _REDIS_RETRY_INTERVAL_SEC = 60.0  # Sau khi fail, chờ 60s mới thử Redis lại

    def __init__(self):
        from src.config import get_settings
        settings = get_settings()

        self._per_user_min = settings.rate_limit_per_user_per_minute
        self._per_entity_min = settings.rate_limit_per_entity_per_minute
        self._per_user_hour = settings.rate_limit_per_user_per_hour

        self._memory = InMemoryRateLimiter()
        self._redis_limiter: RedisRateLimiter | None = None
        self._redis_failed_at: float = 0.0

        self._circuit = CircuitBreaker(
            threshold=settings.circuit_breaker_threshold,
            timeout_sec=settings.circuit_breaker_timeout_sec,
        )

        logger.info(
            "[RATE] Init: user/min=%d, entity/min=%d, user/hour=%d, cb_threshold=%d",
            self._per_user_min, self._per_entity_min,
            self._per_user_hour, self._circuit._threshold,
        )

    async def _get_backend(self):
        """Trả về (backend, is_redis). Tự động fallback memory nếu Redis fail."""
        # Nếu Redis từng fail trong < 60s qua → dùng memory
        if self._redis_failed_at and (time.time() - self._redis_failed_at) < self._REDIS_RETRY_INTERVAL_SEC:
            return self._memory, False

        # Thử lazy init Redis
        if self._redis_limiter is None:
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
                self._redis_limiter = RedisRateLimiter(client)
                self._redis_failed_at = 0.0
                logger.info("[RATE] Redis backend connected")
            except Exception as e:
                self._redis_failed_at = time.time()
                logger.warning("[RATE] Redis unavailable → InMemory: %s", str(e)[:100])
                return self._memory, False

        return self._redis_limiter, True

    def _mark_redis_dead(self):
        """Đánh dấu Redis tạm chết → reset client để lần sau lazy-init lại."""
        self._redis_failed_at = time.time()
        self._redis_limiter = None

    async def _check(self, key: str, limit: int, window_sec: int) -> RateLimitInfo:
        """Internal: thử Redis trước, fallback memory."""
        backend, is_redis = await self._get_backend()
        try:
            return await backend.check(key, limit, window_sec)
        except Exception as e:
            if is_redis:
                logger.warning("[RATE] Redis check error → fallback memory: %s", str(e)[:100])
                self._mark_redis_dead()
                return await self._memory.check(key, limit, window_sec)
            raise

    async def check_rate_limit(
        self,
        user_id: str,
        entity_id: str | None = None,
    ) -> RateLimitInfo:
        """
        Kiểm tra rate limit cho user + entity.
        Returns RateLimitInfo.

        Note: đây là method ASYNC. Caller phải `await`.
        """
        # 1. Per-user per-minute
        result = await self._check(
            key=f"rate:user:{user_id}:min",
            limit=self._per_user_min,
            window_sec=60,
        )
        if result.result == RateLimitResult.RATE_LIMITED:
            logger.warning(
                "[RATE] BLOCKED: user=%s (per-user/min limit=%d)",
                user_id, self._per_user_min,
            )
            return result

        # 2. Per-user per-hour
        result = await self._check(
            key=f"rate:user:{user_id}:hour",
            limit=self._per_user_hour,
            window_sec=3600,
        )
        if result.result == RateLimitResult.RATE_LIMITED:
            logger.warning(
                "[RATE] BLOCKED: user=%s (per-user/hour limit=%d)",
                user_id, self._per_user_hour,
            )
            return result

        # 3. Per-entity per-minute (nếu có entity)
        if entity_id:
            result = await self._check(
                key=f"rate:entity:{entity_id}:min",
                limit=self._per_entity_min,
                window_sec=60,
            )
            if result.result == RateLimitResult.RATE_LIMITED:
                logger.warning(
                    "[RATE] BLOCKED: entity=%s (per-entity/min limit=%d)",
                    entity_id, self._per_entity_min,
                )
                return result

        # Tới đây nghĩa là tất cả check đều ALLOWED → trả result cuối với
        # số `remaining` còn lại để client biết đã dùng bao nhiêu quota.
        return result

    def check_circuit(self) -> RateLimitInfo:
        """Kiểm tra circuit breaker (sync — chỉ dùng in-memory state)."""
        if not self._circuit.allow_request():
            logger.warning("[RATE] CIRCUIT OPEN — rejecting request")
            return RateLimitInfo(
                result=RateLimitResult.CIRCUIT_OPEN,
                reason="Hệ thống tạm ngưng — vui lòng thử lại sau",
            )
        return RateLimitInfo(result=RateLimitResult.ALLOWED)

    @property
    def circuit(self) -> CircuitBreaker:
        return self._circuit


# ── Singleton ────────────────────────────────

_instance: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _instance
    if _instance is None:
        _instance = RateLimiter()
    return _instance
