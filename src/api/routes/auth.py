"""
Auth Routes — Login / Logout / Token Info
==========================================
Xác thực người dùng bằng JWT RS256.

Endpoints:
- POST /auth/login    → Đăng nhập, trả JWT
- POST /auth/logout   → Thu hồi token (blacklist)
- GET  /auth/me       → Xem thông tin user hiện tại

Nguyên tắc bảo mật:
- Password hash bằng bcrypt
- JWT RS256 (asymmetric — an toàn hơn HS256)
- Token ngắn hạn (15 phút)
- Logout = blacklist jti trong Redis
- KHÔNG trả lý do login fail cụ thể (chống enumeration)
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.api.middlewares.auth import (
    CurrentUser,
    get_current_user,
    add_token_to_blacklist,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / Response Models ──────────────────────────────

class LoginRequest(BaseModel):
    """Request body cho login."""
    username: str = Field(
        ..., min_length=1, max_length=50,
        description="Tên đăng nhập",
        examples=["admin"],
    )
    password: str = Field(
        ..., min_length=1, max_length=128,
        description="Mật khẩu",
        examples=["changeme_strong_password_here"],
    )


class TokenResponse(BaseModel):
    """Response sau khi login thành công."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiry
    user_id: str


class LogoutResponse(BaseModel):
    """Response sau khi logout."""
    message: str
    revoked: bool


class MeResponse(BaseModel):
    """Response cho /auth/me."""
    user_id: str
    roles: list[str]
    session_id: str
    expires_at: str


# ── Helper Functions ───────────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash password bằng bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """So sánh password với hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _create_access_token(
    user_id: str,
    roles: list[str],
    settings: Settings,
) -> tuple[str, datetime, str]:
    """
    Tạo JWT access token với RS256.

    Returns:
        (token_string, expires_at, jti)
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    session_id = f"sess_{uuid.uuid4().hex[:12]}"

    expires_at = now + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "roles": roles,
        "session": session_id,
        "iat": now,
        "exp": expires_at,
        "jti": jti,
    }

    private_key = settings.load_jwt_private_key()
    token = jwt.encode(
        payload,
        private_key,
        algorithm=settings.jwt_algorithm,
    )

    return token, expires_at, jti


# ── User "Database" (MVP — single admin user) ─────────────
# Phase 2: Chuyển sang SQLite/Postgres với RBAC

_admin_password_hash: str | None = None


def _get_admin_hash(settings: Settings) -> str:
    """Lazy hash admin password (chỉ hash 1 lần)."""
    global _admin_password_hash
    if _admin_password_hash is None:
        _admin_password_hash = _hash_password(settings.admin_password)
    return _admin_password_hash


def _authenticate_user(
    username: str, password: str, settings: Settings
) -> dict | None:
    """
    Xác thực user.
    MVP: chỉ có 1 admin user từ .env
    Phase 2: query từ database.

    Returns:
        User dict nếu hợp lệ, None nếu sai.
    """
    if username != settings.admin_username:
        return None

    admin_hash = _get_admin_hash(settings)
    if not _verify_password(password, admin_hash):
        return None

    return {
        "user_id": username,
        "roles": ["owner"],  # Admin = owner role
    }


# ── Endpoints ──────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập",
    description="Xác thực user và trả JWT access token.",
)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Đăng nhập bằng username/password.
    Trả về JWT RS256 token (15 phút).
    """
    # Authenticate
    user = _authenticate_user(body.username, body.password, settings)
    if user is None:
        logger.warning("[AUTH] Failed login attempt: user=%s", body.username)
        # Không nói rõ sai username hay password — chống enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Generate JWT
    token, expires_at, jti = _create_access_token(
        user_id=user["user_id"],
        roles=user["roles"],
        settings=settings,
    )

    expires_in = int(
        (expires_at - datetime.now(timezone.utc)).total_seconds()
    )

    logger.info(
        "[AUTH] Login OK: user=%s jti=%s expires_in=%ds",
        user["user_id"], jti[:8], expires_in,
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user_id=user["user_id"],
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Đăng xuất",
    description="Thu hồi JWT token hiện tại (blacklist).",
)
async def logout(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Logout = thêm jti vào Redis blacklist.
    Token không thể dùng lại sau khi logout.
    """
    revoked = await add_token_to_blacklist(user.token_id, user.expires_at)

    logger.info(
        "[AUTH] Logout: user=%s jti=%s revoked=%s",
        user.user_id, user.token_id[:8], revoked,
    )

    return LogoutResponse(
        message="Logged out successfully",
        revoked=revoked,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Thông tin user",
    description="Xem thông tin của user đang đăng nhập.",
)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
):
    """Trả về thông tin user từ JWT payload."""
    return MeResponse(
        user_id=user.user_id,
        roles=user.roles,
        session_id=user.session_id,
        expires_at=user.expires_at.isoformat(),
    )
