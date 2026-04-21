"""
JWT Authentication Middleware
==============================
FastAPI dependency injection cho JWT validation.

Validation checklist (theo thứ tự):
1. Header Authorization: Bearer <token> tồn tại
2. Token format hợp lệ
3. Chữ ký hợp lệ (RS256 với public key)
4. Token chưa hết hạn (exp)
5. jti không có trong Redis blacklist
6. Trả về user context (sub, roles, session)

Nguyên tắc bảo mật:
- KHÔNG lộ lý do cụ thể khi reject (chỉ 401 chung)
- KHÔNG trả stack trace trong response
- Log chi tiết phía server để debug
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

# FastAPI security scheme — tự extract Bearer token từ header
security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """
    User context được inject vào mọi protected route.
    Immutable (frozen) để đảm bảo không ai sửa được sau khi validate.
    """
    user_id: str          # sub
    roles: list[str]      # ["owner"] hoặc ["guest"]
    session_id: str       # Session tracking
    token_id: str         # jti — dùng cho blacklist
    expires_at: datetime  # Thời điểm token hết hạn


# ── Redis client singleton (lazy init) ─────────────────────
_redis_client = None


async def _get_redis():
    """Lazy init Redis client — tránh import error khi Redis chưa sẵn sàng."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            settings = get_settings()
            _redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            # Test connection
            await _redis_client.ping()
            logger.info("[AUTH] Redis connected for JWT blacklist")
        except Exception as e:
            logger.warning(
                "[AUTH] Redis unavailable — blacklist disabled: %s", e
            )
            _redis_client = None
    return _redis_client


async def _is_token_blacklisted(jti: str) -> bool:
    """Kiểm tra token đã bị revoke (logout) chưa."""
    redis = await _get_redis()
    if redis is None:
        # Redis down → cho phép (fail-open cho dev, fail-close cho prod)
        settings = get_settings()
        if settings.is_production:
            logger.error("[AUTH] Redis down in production — blocking request")
            return True  # Fail-close trong production
        return False  # Fail-open trong dev
    try:
        result = await redis.exists(f"jwt:blacklist:{jti}")
        return bool(result)
    except Exception as e:
        logger.error("[AUTH] Redis error checking blacklist: %s", e)
        return False


async def add_token_to_blacklist(jti: str, expires_at: datetime) -> bool:
    """
    Thêm token vào blacklist khi logout.
    TTL = thời gian còn lại của token (tự clean up).
    """
    redis = await _get_redis()
    if redis is None:
        logger.warning("[AUTH] Cannot blacklist token — Redis unavailable")
        return False
    try:
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if ttl <= 0:
            return True  # Token đã hết hạn, không cần blacklist
        await redis.setex(f"jwt:blacklist:{jti}", ttl, "revoked")
        logger.info("[AUTH] Token %s blacklisted (TTL=%ds)", jti[:8], ttl)
        return True
    except Exception as e:
        logger.error("[AUTH] Failed to blacklist token: %s", e)
        return False


def _decode_token(token: str, settings: Settings) -> dict:
    """
    Decode và validate JWT token.
    Raises jwt.PyJWTError nếu token invalid.
    """
    public_key = settings.load_jwt_public_key()
    return jwt.decode(
        token,
        public_key,
        algorithms=[settings.jwt_algorithm],
        options={
            "require": ["sub", "exp", "iat", "jti"],
            "verify_exp": True,
            "verify_iat": True,
        },
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """
    FastAPI dependency — inject CurrentUser vào protected routes.

    Usage:
        @router.post("/chat")
        async def chat(user: CurrentUser = Depends(get_current_user)):
            ...
    """
    # ── Step 1: Check Authorization header ─────────────────
    if credentials is None:
        logger.warning(
            "[AUTH] Missing Authorization header from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── Step 2-4: Decode + Validate signature + Check expiry ─
    try:
        payload = _decode_token(token, settings)
    except jwt.ExpiredSignatureError:
        logger.warning("[AUTH] Expired token from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("[AUTH] Invalid token: %s", str(e)[:100])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Step 5: Check blacklist ────────────────────────────
    jti = payload.get("jti", "")
    if await _is_token_blacklisted(jti):
        logger.warning("[AUTH] Blacklisted token used: jti=%s", jti[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Step 6: Build user context ─────────────────────────
    return CurrentUser(
        user_id=payload.get("sub", "unknown"),
        roles=payload.get("roles", []),
        session_id=payload.get("session", ""),
        token_id=jti,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
