"""
User Management Routes — Quản lý tài khoản
=============================================
Chỉ Owner mới có quyền tạo/xoá/liệt kê user.

Endpoints:
- GET    /users         → Danh sách users
- POST   /users         → Tạo user mới
- DELETE /users/{uid}   → Xoá user
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config import get_settings
from src.api.middlewares.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["User Management"])

# ── User Storage (JSON file) ──────────────────────────────
# MVP: Lưu users vào file JSON thay vì DB phức tạp
# File: ./data/users.json

USERS_FILE = Path("./data/users.json")


def _ensure_data_dir():
    """Tạo thư mục data nếu chưa có."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")


def _load_users() -> list[dict]:
    """Đọc danh sách users từ file."""
    _ensure_data_dir()
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_users(users: list[dict]):
    """Ghi danh sách users vào file."""
    _ensure_data_dir()
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


# ── Request / Response Models ──────────────────────────────

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="Tên đăng nhập")
    password: str = Field(..., min_length=4, max_length=128, description="Mật khẩu")
    display_name: str = Field(default="", max_length=100, description="Tên hiển thị")
    role: str = Field(default="guest", description="Quyền: owner hoặc guest")


class UserResponse(BaseModel):
    username: str
    display_name: str
    role: str
    created_at: str
    auth_method: str = "local"  # local | google


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


# ── Owner-only guard ──────────────────────────────────────

def _require_owner(user: CurrentUser):
    """Kiểm tra user có phải owner không."""
    if "owner" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Owner mới có quyền quản lý tài khoản.",
        )


# ── Endpoints ──────────────────────────────────────────────

@router.get(
    "",
    response_model=UserListResponse,
    summary="Danh sách tài khoản",
    description="Lấy danh sách tất cả tài khoản (chỉ Owner).",
)
async def list_users(
    user: CurrentUser = Depends(get_current_user),
):
    _require_owner(user)

    settings = get_settings()
    users = _load_users()

    # Thêm admin & guest mặc định vào danh sách (luôn tồn tại)
    result = [
        UserResponse(
            username=settings.admin_username,
            display_name="Admin",
            role="owner",
            created_at="—",
            auth_method="local (mặc định)",
        ),
        UserResponse(
            username=settings.guest_username,
            display_name="Guest",
            role="guest",
            created_at="—",
            auth_method="local (mặc định)",
        ),
    ]

    # Thêm users tự tạo
    for u in users:
        result.append(UserResponse(
            username=u["username"],
            display_name=u.get("display_name", u["username"]),
            role=u.get("role", "guest"),
            created_at=u.get("created_at", "—"),
            auth_method="local",
        ))

    logger.info("[USERS] List: %d users (by %s)", len(result), user.user_id)

    return UserListResponse(users=result, total=len(result))


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản mới",
    description="Tạo tài khoản local mới (chỉ Owner).",
)
async def create_user(
    body: CreateUserRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _require_owner(user)

    settings = get_settings()
    users = _load_users()

    # Kiểm tra trùng username
    reserved = [settings.admin_username, settings.guest_username]
    existing = [u["username"] for u in users]

    if body.username.lower() in [r.lower() for r in reserved + existing]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tài khoản '{body.username}' đã tồn tại.",
        )

    # Validate role
    if body.role not in ("owner", "guest"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role phải là 'owner' hoặc 'guest'.",
        )

    # Tạo user mới
    new_user = {
        "username": body.username,
        "password_hash": _hash_pw(body.password),
        "display_name": body.display_name or body.username,
        "role": body.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    users.append(new_user)
    _save_users(users)

    logger.info(
        "[USERS] Created: %s (role=%s) by %s",
        body.username, body.role, user.user_id,
    )

    return UserResponse(
        username=new_user["username"],
        display_name=new_user["display_name"],
        role=new_user["role"],
        created_at=new_user["created_at"],
        auth_method="local",
    )


@router.delete(
    "/{username}",
    summary="Xoá tài khoản",
    description="Xoá tài khoản (chỉ Owner, không xoá được admin/guest mặc định).",
)
async def delete_user(
    username: str,
    user: CurrentUser = Depends(get_current_user),
):
    _require_owner(user)

    settings = get_settings()

    # Không cho xoá tài khoản mặc định
    if username.lower() in (settings.admin_username.lower(), settings.guest_username.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xoá tài khoản mặc định.",
        )

    users = _load_users()
    new_users = [u for u in users if u["username"] != username]

    if len(new_users) == len(users):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản '{username}'.",
        )

    _save_users(new_users)
    logger.info("[USERS] Deleted: %s by %s", username, user.user_id)

    return {"message": f"Đã xoá tài khoản '{username}'.", "deleted": True}


class UpdateUserRequest(BaseModel):
    """Request body cập nhật user."""
    display_name: str | None = Field(default=None, max_length=100)
    role: str | None = Field(default=None)
    password: str | None = Field(default=None, min_length=4, max_length=128)


@router.put(
    "/{username}",
    response_model=UserResponse,
    summary="Sửa tài khoản",
    description="Cập nhật thông tin tài khoản (chỉ Owner, không sửa được admin/guest mặc định).",
)
async def update_user(
    username: str,
    body: UpdateUserRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _require_owner(user)

    settings = get_settings()

    # Không cho sửa tài khoản mặc định
    if username.lower() in (settings.admin_username.lower(), settings.guest_username.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể sửa tài khoản mặc định.",
        )

    users = _load_users()
    found = False

    for u in users:
        if u["username"] == username:
            found = True
            if body.display_name is not None:
                u["display_name"] = body.display_name
            if body.role is not None:
                if body.role not in ("owner", "guest"):
                    raise HTTPException(status_code=400, detail="Role phải là 'owner' hoặc 'guest'.")
                u["role"] = body.role
            if body.password is not None:
                u["password_hash"] = _hash_pw(body.password)
            break

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản '{username}'.",
        )

    _save_users(users)
    logger.info("[USERS] Updated: %s by %s", username, user.user_id)

    target = next(u for u in users if u["username"] == username)
    return UserResponse(
        username=target["username"],
        display_name=target.get("display_name", username),
        role=target.get("role", "guest"),
        created_at=target.get("created_at", "—"),
        auth_method="local",
    )
