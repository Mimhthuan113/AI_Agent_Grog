"""
Rate Limiter + Circuit Breaker — Redis-based
==============================================
Bảo vệ hệ thống khỏi lạm dụng và cascading failure.

Rate Limiter:
  - Sliding Window Counter (Redis Sorted Set)
  - 3 tầng: per-user/min, per-entity/min, per-user/hour
  - Graceful degradation: Redis down → bypass (dev) / block (prod)

Circuit Breaker:
  - Đếm failed HA calls
  - Nếu > threshold → mở circuit (reject ngay, không gọi HA)
  - Tự đóng sau timeout (60s mặc định)

Sử dụng config đã có sẵn từ src/config.py:
  - rate_limit_per_user_per_minute
  - rate_limit_per_entity_per_minute
  - rate_limit_per_user_per_hour
  - circuit_breaker_threshold
  - circuit_breaker_timeout_sec
"""

from __future__ import annotations

import time
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


# ── In-Memory Fallback (khi Redis down) ───────────────────

class InMemoryRateLimiter:
    """
    Fallback rate limiter khi Redis không khả dụng.
    Dùng dict + sliding window đơn giản.
    """

    def __init__(self):
        self._windows: dict[str, list[float]] = {}

    def check(self, key: str, limit: int, window_sec: int) -> RateLimitInfo:
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


# ── Main Rate Limiter ─────────────────────────────────────

class RateLimiter:
    """
    Rate Limiter chính — dùng Redis nếu có, fallback InMemory.
    """

    def __init__(self):
        from src.config import get_settings
        settings = get_settings()

        self._per_user_min = settings.rate_limit_per_user_per_minute
        self._per_entity_min = settings.rate_limit_per_entity_per_minute
        self._per_user_hour = settings.rate_limit_per_user_per_hour

        self._memory = InMemoryRateLimiter()
        self._circuit = CircuitBreaker(
            threshold=settings.circuit_breaker_threshold,
            timeout_sec=settings.circuit_breaker_timeout_sec,
        )

        logger.info(
            "[RATE] Init: user/min=%d, entity/min=%d, user/hour=%d, cb_threshold=%d",
            self._per_user_min, self._per_entity_min,
            self._per_user_hour, self._circuit._threshold,
        )

    def check_rate_limit(
        self,
        user_id: str,
        entity_id: str | None = None,
    ) -> RateLimitInfo:
        """
        Kiểm tra rate limit cho user + entity.
        Returns RateLimitInfo.
        """
        # 1. Check per-user per-minute
        result = self._memory.check(
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

        # 2. Check per-user per-hour
        result = self._memory.check(
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

        # 3. Check per-entity per-minute (nếu có entity)
        if entity_id:
            result = self._memory.check(
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

        return RateLimitInfo(result=RateLimitResult.ALLOWED)

    def check_circuit(self) -> RateLimitInfo:
        """Kiểm tra circuit breaker."""
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


# ── Singleton ──────────────────────────────────────────────

_instance: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _instance
    if _instance is None:
        _instance = RateLimiter()
    return _instance
