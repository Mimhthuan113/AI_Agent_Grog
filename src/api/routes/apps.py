"""
Apps Route — API cho App Actions
===================================
Quản lý và thực thi app actions (mở app, gọi, nhắn, tìm kiếm...).

Endpoints:
- GET  /apps                    → Danh sách apps + capabilities
- POST /apps/execute            → Thực thi app action
- GET  /apps/detected           → Quét app đã cài trên máy & trạng thái quyền
- POST /apps/permission         → Cấp / Chặn / Reset quyền một app
- GET  /apps/automation-status  → Trạng thái UI Agent
- POST /apps/stop-automation    → Dừng UI Agent
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.middlewares.auth import CurrentUser, get_current_user
from src.core.app_actions.router import get_all_capabilities, execute_app_action, parse_app_intent
from src.core.app_actions.permissions import (
    is_provider_allowed, deny_message, get_permissions_store,
    PermissionsStore, app_permission_status,
)
from src.core.app_actions.ui_agent import is_automation_running, request_stop_automation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apps", tags=["App Actions"])


class AppActionRequest(BaseModel):
    """Request body cho app action."""
    provider: str = Field(..., description="Tên provider (zalo, phone, youtube...)")
    action: str = Field(..., description="Tên action (open_zalo, call, youtube_search...)")
    params: dict = Field(default_factory=dict, description="Tham số")


class AppActionResponse(BaseModel):
    """Response cho app action."""
    success: bool
    message: str
    intent_uri: str | None = None
    data: dict | None = None
    provider: str = ""
    action: str = ""


class PermissionRequest(BaseModel):
    """Body cho cấp / chặn quyền app."""
    key: str = Field(..., description="Provider key (vd: zalo, chrome...)")
    action: str = Field(..., description="'grant' | 'block' | 'reset' | 'grant_all'")


@router.get(
    "",
    summary="Danh sách ứng dụng",
    description="Xem tất cả app providers và capabilities.",
)
async def list_apps(user: CurrentUser = Depends(get_current_user)):
    """Trả về danh sách toàn bộ app providers."""
    return get_all_capabilities()


@router.post(
    "/execute",
    response_model=AppActionResponse,
    summary="Thực thi app action",
    description="Gửi lệnh tới app provider. RBAC theo whitelist.",
)
async def execute_action(
    body: AppActionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Thực thi app action."""
    if not is_provider_allowed(body.provider, user.roles):
        logger.info("[APPS] RBAC denied: user=%s provider=%s", user.user_id, body.provider)
        return AppActionResponse(
            success=False,
            message=deny_message(body.provider),
            provider=body.provider,
            action=body.action,
        )

    result = await execute_app_action(body.provider, body.action, body.params)
    return AppActionResponse(
        success=result.success,
        message=result.message,
        intent_uri=result.intent_uri,
        data=result.data,
        provider=result.provider,
        action=result.action,
    )


@router.get(
    "/detected",
    summary="Quét ứng dụng đã cài",
    description=(
        "Quét toàn bộ app đã cài trên Windows (Registry + Start Menu). "
        "Trả về kèm trạng thái quyền (pending/granted/blocked). "
        "?refresh=true để reset cache và quét lại."
    ),
)
async def detected_apps(
    refresh: bool = False,
    user: CurrentUser = Depends(get_current_user),
):
    """Quét máy thật sự — catalog quét được là chính, known apps chỉ là fallback Windows/UWP."""
    import src.core.app_actions.app_discovery as _disc
    from src.core.app_actions.app_discovery import get_discovered_apps, normalize_app_name
    from src.core.app_actions.system_executor import KNOWN_APPS, _find_app_exe

    if refresh:
        _disc._discovered_apps = None
        logger.info("[APPS] App cache reset by user=%s", user.user_id)

    store: PermissionsStore = get_permissions_store()

    def _scan() -> list[dict]:
        discovered = get_discovered_apps()  # { "key_lower": {display, exe_path, source} }

        result: list[dict] = []
        seen_names: set[str] = set()
        seen_paths: set[str] = set()

        for disc_key, disc_info in discovered.items():
            perm_key = f"disc:{disc_key}"
            status = app_permission_status(perm_key)
            exe_path = disc_info.get("exe_path")
            result.append({
                "key":        perm_key,
                "name":       disc_info["display"],
                "installed":  True,
                "status":     status,
                "granted":    status == PermissionsStore.STATUS_GRANTED,
                "blocked":    status == PermissionsStore.STATUS_BLOCKED,
                "exe_path":   exe_path,
                "uwp":        False,
                "source":     disc_info.get("source", "registry"),
            })
            seen_names.add(normalize_app_name(disc_info["display"]))
            if exe_path:
                seen_paths.add(exe_path.lower())

        # Fallback only: giữ mấy shortcut Windows/UWP nếu scanner không trả về.
        for app_key, info in KNOWN_APPS.items():
            if app_key.startswith("_discovered_"):
                continue
            display_norm = normalize_app_name(info["display"])
            exe_path = _find_app_exe(app_key)
            if display_norm in seen_names:
                continue
            if exe_path and not exe_path.startswith("uwp:") and exe_path.lower() in seen_paths:
                continue

            status = app_permission_status(app_key)
            result.append({
                "key":        app_key,
                "name":       info["display"],
                "installed":  bool(exe_path),
                "status":     status,
                "granted":    status == PermissionsStore.STATUS_GRANTED,
                "blocked":    status == PermissionsStore.STATUS_BLOCKED,
                "exe_path":   None if exe_path and exe_path.startswith("uwp:") else exe_path,
                "uwp":        bool(info.get("uwp")),
                "source":     "known",
            })
            seen_names.add(display_norm)
            if exe_path and not exe_path.startswith("uwp:"):
                seen_paths.add(exe_path.lower())

        def sort_key(a):
            installed = 0 if a["installed"] else 2
            source = 0 if a["source"] != "known" else 1
            return (installed, source, a["name"].lower())

        return sorted(result, key=sort_key)

    apps = await asyncio.to_thread(_scan)
    summary = store.summary()
    installed_count = sum(1 for a in apps if a["installed"])
    return {
        "total":     len(apps),
        "installed": installed_count,
        "granted":   summary["granted"],
        "blocked":   summary["blocked"],
        "apps":      apps,
    }


@router.post(
    "/permission",
    summary="Cấp / Chặn / Reset quyền app",
    description=(
        "action = 'grant' → cấp quyền | 'block' → chặn | "
        "'reset' → về pending | 'grant_all' → cấp tất cả đã cài."
    ),
)
async def set_permission(
    body: PermissionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Chỉ owner mới được thay đổi quyền app."""
    if "owner" not in user.roles:
        raise HTTPException(status_code=403, detail="Chỉ chủ nhà mới có thể cấp quyền app.")

    from src.core.app_actions.system_executor import KNOWN_APPS, _find_app_exe
    store: PermissionsStore = get_permissions_store()

    act = body.action.strip().lower()

    if act == "grant_all":
        # Cấp theo catalog quét được trước; known apps chỉ bù các shortcut Windows/UWP.
        from src.core.app_actions.app_discovery import get_discovered_apps, normalize_app_name

        discovered = await asyncio.to_thread(get_discovered_apps)
        all_keys: list[str] = [f"disc:{dk}" for dk in discovered.keys()]
        discovered_names = {
            normalize_app_name(info["display"])
            for info in discovered.values()
            if info.get("display")
        }
        discovered_paths = {
            info["exe_path"].lower()
            for info in discovered.values()
            if info.get("exe_path")
        }

        for key, info in KNOWN_APPS.items():
            if key.startswith("_discovered_"):
                continue
            exe_path = _find_app_exe(key)
            if not exe_path:
                continue
            if normalize_app_name(info["display"]) in discovered_names:
                continue
            if not exe_path.startswith("uwp:") and exe_path.lower() in discovered_paths:
                continue
            all_keys.append(key)

        count = await asyncio.to_thread(store.grant_all, all_keys)
        return {"success": True, "message": f"Đã cấp quyền cho {count} ứng dụng đã cài."}

    key = body.key.strip()

    # disc:{name} là key chính từ scanner; known key chỉ để bù shortcut fallback.
    if key.startswith("disc:"):
        disc_name = key[5:]
        discovered = await asyncio.to_thread(
            lambda: __import__('src.core.app_actions.app_discovery', fromlist=['get_discovered_apps']).get_discovered_apps()
        )
        if disc_name not in discovered:
            raise HTTPException(status_code=400, detail=f"App '{disc_name}' không tìm thấy.")
        app_name = discovered[disc_name]["display"]
    else:
        from src.core.app_actions.system_executor import KNOWN_APPS
        if not key or key not in KNOWN_APPS:
            raise HTTPException(status_code=400, detail=f"App key '{key}' không hợp lệ.")
        app_name = KNOWN_APPS[key]["display"]

    if act == "grant":
        store.grant(key)
        return {"success": True, "message": f"Đã cấp quyền cho {app_name}.", "status": "granted"}
    elif act == "block":
        store.block(key)
        return {"success": True, "message": f"Đã chặn {app_name}.", "status": "blocked"}
    elif act == "reset":
        store.reset(key)
        return {"success": True, "message": f"Đã đặt lại quyền của {app_name}.", "status": "pending"}
    else:
        raise HTTPException(status_code=400, detail=f"action '{act}' không hợp lệ. Dùng: grant | block | reset | grant_all")


@router.get(
    "/automation-status",
    summary="Trạng thái UI Agent",
    description="Kiểm tra UI Agent có đang chạy không.",
)
async def automation_status(user: CurrentUser = Depends(get_current_user)):
    """Trả về trạng thái automation hiện tại."""
    return {"running": is_automation_running()}


@router.post(
    "/stop-automation",
    summary="Dừng UI Agent",
    description="Yêu cầu dừng UI Agent đang chạy.",
)
async def stop_automation(user: CurrentUser = Depends(get_current_user)):
    """Dừng UI Agent nếu đang chạy — chỉ owner/admin mới được phép."""
    if "owner" not in user.roles and "admin" not in user.roles:
        logger.warning("[APPS] stop-automation denied: user=%s roles=%s", user.user_id, user.roles)
        raise HTTPException(status_code=403, detail="Chỉ owner/admin mới có thể dừng automation.")
    stopped = request_stop_automation()
    logger.info("[APPS] Stop automation: user=%s, was_running=%s", user.user_id, stopped)
    return {
        "success": True,
        "stopped": stopped,
        "message": "Đã gửi lệnh dừng." if stopped else "Không có automation đang chạy.",
    }
