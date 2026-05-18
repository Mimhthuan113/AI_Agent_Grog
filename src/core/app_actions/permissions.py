"""
App Actions — Phân quyền theo role + Quản lý quyền ứng dụng động
=================================================================
Owner: full control (mọi provider, kể cả file_ops, system_app).
Guest: chỉ provider an toàn (gọi/nhắn/giải trí/báo thức) — KHÔNG được
       tạo file/folder, KHÔNG mở app hệ thống tuỳ ý, KHÔNG cấu hình OS.

Khi thêm provider mới mà muốn cho guest dùng → thêm vào set bên dưới.

PermissionsStore: lưu trạng thái cấp phép từng app theo provider key.
- Mặc định: chưa cấp (pending)
- Owner cấp: granted
- Owner chặn: blocked
"""
from __future__ import annotations

from typing import Iterable
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)

PERMISSIONS_FILE = Path(__file__).resolve().parents[3] / "data" / "app_permissions.json"

# ── Whitelist provider cho guest ──────────────────────────────
# KHÔNG bao gồm: file_ops, system_app (mở Notepad, This PC, Settings…)
GUEST_ALLOWED_PROVIDERS: frozenset[str] = frozenset({
    "phone",      # gọi điện
    "sms",        # nhắn tin
    "zalo",       # zalo
    "facebook",   # fb / messenger
    "youtube",    # youtube
    "spotify",    # spotify
    "tiktok",     # tiktok
    "maps",       # google maps / chỉ đường
    "gmail",      # email
    "camera",     # camera chụp ảnh
    "web",        # tìm kiếm web
    "coccoc",     # cốc cốc
    "alarm",      # đặt báo thức / mở đồng hồ
})


def is_provider_allowed(provider: str, user_roles: Iterable[str] | None) -> bool:
    """
    True nếu user có quyền dùng provider này.

    - owner: luôn True (full control).
    - guest: True chỉ khi `provider` thuộc GUEST_ALLOWED_PROVIDERS.
    - không có role: False.
    """
    roles = list(user_roles or [])
    if "owner" in roles:
        return True
    if "guest" in roles:
        return provider in GUEST_ALLOWED_PROVIDERS
    return False


def deny_message(provider: str) -> str:
    """Thông báo từ chối thân thiện."""
    return (
        f"Xin lỗi, quyền của bạn không cho phép sử dụng '{provider}'. "
        "Hãy nhờ chủ nhà cấp quyền hoặc thử thao tác cơ bản khác."
    )


# ══════════════════════════════════════════════════════════════
# PermissionsStore — Quản lý quyền ứng dụng trên máy cụ thể
# ══════════════════════════════════════════════════════════════

class PermissionsStore:
    """
    Lưu trạng thái quyền từng provider/app.

    Trạng thái:
        "pending"  — chưa quyết định (chờ duyệt)
        "granted"  — đã cấp (Aisha được dùng)
        "blocked"  — đã chặn (Aisha không được dùng)
    """

    STATUS_PENDING = "pending"
    STATUS_GRANTED = "granted"
    STATUS_BLOCKED = "blocked"

    def __init__(self) -> None:
        # { provider_key: status }
        self._store: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        try:
            if not PERMISSIONS_FILE.exists():
                return {}
            data = json.loads(PERMISSIONS_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            valid = {self.STATUS_PENDING, self.STATUS_GRANTED, self.STATUS_BLOCKED}
            return {str(k): str(v) for k, v in data.items() if str(v) in valid}
        except Exception as exc:
            logger.warning("[PERMS] Load failed: %s", str(exc)[:100])
            return {}

    def _save(self) -> None:
        try:
            PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            PERMISSIONS_FILE.write_text(
                json.dumps(self._store, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[PERMS] Save failed: %s", str(exc)[:100])

    def get_status(self, key: str) -> str:
        return self._store.get(key, self.STATUS_PENDING)

    def grant(self, key: str) -> None:
        self._store[key] = self.STATUS_GRANTED
        self._save()
        logger.info("[PERMS] Granted: %s", key)

    def block(self, key: str) -> None:
        self._store[key] = self.STATUS_BLOCKED
        self._save()
        logger.info("[PERMS] Blocked: %s", key)

    def reset(self, key: str) -> None:
        self._store.pop(key, None)
        self._save()
        logger.info("[PERMS] Reset: %s", key)

    def grant_all(self, keys: list[str]) -> int:
        count = 0
        for k in keys:
            if self._store.get(k) != self.STATUS_GRANTED:
                self._store[k] = self.STATUS_GRANTED
                count += 1
        self._save()
        logger.info("[PERMS] Grant all: %d apps", count)
        return count

    def is_granted(self, key: str) -> bool:
        return self._store.get(key) == self.STATUS_GRANTED

    def is_granted_any(self, keys: Iterable[str]) -> bool:
        return any(self.is_granted(k) for k in keys)

    def is_blocked(self, key: str) -> bool:
        return self._store.get(key) == self.STATUS_BLOCKED

    def is_blocked_any(self, keys: Iterable[str]) -> bool:
        return any(self.is_blocked(k) for k in keys)

    def summary(self) -> dict[str, int]:
        granted = sum(1 for s in self._store.values() if s == self.STATUS_GRANTED)
        blocked = sum(1 for s in self._store.values() if s == self.STATUS_BLOCKED)
        return {"granted": granted, "blocked": blocked, "pending": len(self._store) - granted - blocked}


# Singleton — dùng chung toàn app
_store = PermissionsStore()


def get_permissions_store() -> PermissionsStore:
    """Lấy singleton PermissionsStore."""
    return _store


def app_permission_status(app_key: str) -> str:
    """Return granted/blocked/pending for a local app key, including equivalent keys."""
    from src.core.app_actions.system_executor import equivalent_permission_keys

    store = get_permissions_store()
    keys = equivalent_permission_keys(app_key)
    if store.is_blocked_any(keys):
        return PermissionsStore.STATUS_BLOCKED
    if store.is_granted_any(keys):
        return PermissionsStore.STATUS_GRANTED
    return PermissionsStore.STATUS_PENDING


def is_local_app_granted(app_key: str) -> bool:
    return app_permission_status(app_key) == PermissionsStore.STATUS_GRANTED


def local_app_permission_message(app_key: str) -> str:
    from src.core.app_actions.system_executor import get_app_display_name

    name = get_app_display_name(app_key)
    status = app_permission_status(app_key)
    if status == PermissionsStore.STATUS_BLOCKED:
        return f"Ứng dụng {name} đang bị chặn. Hãy mở trang Tài khoản để bỏ chặn/cấp quyền lại."
    return f"Ứng dụng {name} chưa được cấp quyền. Hãy quét app và bấm cấp quyền trước khi Aisha điều khiển."
