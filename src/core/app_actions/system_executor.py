"""
System Executor — Thực thi lệnh hệ thống trên máy tính
=========================================================
AI Agent THẬT SỰ — không chỉ mở URL trong browser.

Khả năng:
- Mở bất kỳ ứng dụng nào đã quét được từ Registry/Start Menu
- Mở URL bằng trình duyệt MẶC ĐỊNH (không chỉ Chrome)
- Tìm kiếm trên YouTube, Google Maps... bằng trình duyệt mặc định

Bảo mật: Chỉ owner mới có quyền — RBAC đã enforce ở agent.py
"""
from __future__ import annotations

import os
import logging
import subprocess
import webbrowser
import shutil
import re

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# App Registry — fallback Windows/UWP shortcuts only
# ══════════════════════════════════════════════════════════════

# App local cài thêm được mở từ catalog quét được trong app_discovery.
# Bảng này chỉ giữ shortcut hệ thống mà scanner Windows hay không trả về.
KNOWN_APPS: dict[str, dict] = {
    # System
    "notepad": {
        "exe": ["notepad.exe"],
        "paths": [r"C:\Windows\System32\notepad.exe"],
        "display": "Notepad",
    },
    "explorer": {
        "exe": ["explorer.exe"],
        "paths": [r"C:\Windows\explorer.exe"],
        "display": "File Explorer",
    },
    "calculator": {
        "exe": ["calc.exe", "Calculator.exe"],
        "paths": [],
        "display": "Máy tính",
        "uwp": "calculator:",
    },
    "settings": {
        "exe": [],
        "paths": [],
        "display": "Cài đặt",
        "uwp": "ms-settings:",
    },
    "camera": {
        "exe": [],
        "paths": [],
        "display": "Camera",
        "uwp": "microsoft.windows.camera:",
    },
    "clock": {
        "exe": [],
        "paths": [],
        "display": "Đồng hồ & Báo thức",
        "uwp": "ms-clock:",
    },
    "alarm": {
        "exe": [],
        "paths": [],
        "display": "Đồng hồ & Báo thức",
        "uwp": "ms-clock:alarm",
    },
    "paint": {
        "exe": ["mspaint.exe"],
        "paths": [r"C:\Windows\System32\mspaint.exe"],
        "display": "Paint",
    },
    "cmd": {
        "exe": ["cmd.exe"],
        "paths": [r"C:\Windows\System32\cmd.exe"],
        "display": "Command Prompt",
    },
    "powershell": {
        "exe": ["powershell.exe"],
        "paths": [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"],
        "display": "PowerShell",
    },
    "task_manager": {
        "exe": ["Taskmgr.exe"],
        "paths": [r"C:\Windows\System32\Taskmgr.exe"],
        "display": "Task Manager",
    },
}

# Alias fallback cho shortcut hệ thống; app cài thêm được resolve bằng scanner.
APP_ALIASES: dict[str, str] = {
    "notepad": "notepad", "note pad": "notepad",
    "file explorer": "explorer", "explorer": "explorer",
    "this pc": "explorer", "thư mục": "explorer", "thu muc": "explorer",
    "folder": "explorer", "foder": "explorer",
    "máy tính": "calculator", "may tinh": "calculator", "calculator": "calculator",
    "calc": "calculator",
    "cài đặt": "settings", "cai dat": "settings", "settings": "settings",
    "camera": "camera",
    "đồng hồ": "clock", "dong ho": "clock", "clock": "clock",
    "báo thức": "alarm", "bao thuc": "alarm", "alarm": "alarm",
    "paint": "paint",
    "cmd": "cmd", "command prompt": "cmd",
    "powershell": "powershell",
    "task manager": "task_manager", "taskmgr": "task_manager",
}


def _clean_app_query(text: str) -> str:
    """Remove common command filler around an app name."""
    cleaned = (text or "").lower().strip()
    cleaned = re.sub(
        r"^(?:mở|mo|mở\s+app|mo\s+app|vào|vao|chạy|chay|bật|bat|open|launch)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    while True:
        next_cleaned = re.sub(
            r"\s+(?:lên|len|đi|di|rồi|roi|rùi|rui|và|va|xong|giùm|gium|giúp|giup|cho\s+tui|cho\s+tôi|cho\s+toi|tui|nhé|nhe)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    return cleaned.strip()


def _discovered_key(display_or_key: str) -> str:
    return f"disc:{display_or_key.lower().strip()}"


def _get_discovered_app_by_key(app_key: str) -> dict | None:
    if not app_key.startswith("disc:"):
        return None
    disc_key = app_key[5:].lower().strip()
    try:
        from src.core.app_actions.app_discovery import get_discovered_apps

        return get_discovered_apps().get(disc_key)
    except Exception as exc:
        logger.warning("[SYS_EXEC] Discovered lookup error: %s", str(exc)[:100])
        return None


def _find_discovered_app_key(query: str) -> tuple[str | None, str, str | None]:
    """Return (permission key, display name, exe path) for a scanned app."""
    cleaned = _clean_app_query(query)
    if not cleaned:
        return None, query, None

    try:
        from src.core.app_actions.app_discovery import get_discovered_apps, search_installed_app

        discovered = search_installed_app(cleaned)
        if not discovered:
            return None, query, None

        apps = get_discovered_apps()
        disc_key = next(
            (
                key
                for key, info in apps.items()
                if info.get("exe_path") == discovered.get("exe_path")
                or info.get("display") == discovered.get("display")
            ),
            discovered.get("display", cleaned).lower().strip(),
        )
        return _discovered_key(disc_key), discovered["display"], discovered["exe_path"]
    except Exception as exc:
        logger.warning("[SYS_EXEC] Discovery resolve error: %s", str(exc)[:100])
        return None, query, None


def get_app_display_name(app_key: str) -> str:
    discovered = _get_discovered_app_by_key(app_key)
    if discovered:
        return discovered.get("display", app_key)
    return KNOWN_APPS.get(app_key, {}).get("display", app_key)


def equivalent_permission_keys(app_key: str) -> list[str]:
    """Known and scanned keys that refer to the same app."""
    keys = [app_key]

    discovered = _get_discovered_app_by_key(app_key)
    if discovered:
        display = discovered.get("display", "")
        disc_path = (discovered.get("exe_path") or "").lower()
        for known_key, info in KNOWN_APPS.items():
            if info.get("display", "").lower() == display.lower():
                keys.append(known_key)
                continue
            known_path = _find_app_exe(known_key)
            if disc_path and known_path and not known_path.startswith("uwp:") and known_path.lower() == disc_path:
                keys.append(known_key)
        return list(dict.fromkeys(keys))

    app = KNOWN_APPS.get(app_key)
    if app:
        disc_key, _, _ = _find_discovered_app_key(app.get("display", app_key))
        if disc_key:
            keys.append(disc_key)

    return list(dict.fromkeys(keys))


def _find_app_paths_registry(exe_name: str) -> str | None:
    """Find an executable registered in Windows App Paths."""
    if os.name != "nt":
        return None

    try:
        import winreg
    except ImportError:
        return None

    reg_paths = [
        rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
        rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
    ]
    hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]

    for hive in hives:
        for reg_path in reg_paths:
            try:
                with winreg.OpenKey(hive, reg_path) as key:
                    try:
                        raw_path = winreg.QueryValueEx(key, "")[0]
                    except FileNotFoundError:
                        raw_path = ""

                    clean_path = os.path.expandvars(str(raw_path)).strip().strip('"')
                    if clean_path and os.path.isfile(clean_path):
                        return clean_path

                    try:
                        raw_dir = winreg.QueryValueEx(key, "Path")[0]
                    except FileNotFoundError:
                        raw_dir = ""

                    clean_dir = os.path.expandvars(str(raw_dir)).strip().strip('"')
                    candidate = os.path.join(clean_dir, exe_name)
                    if clean_dir and os.path.isfile(candidate):
                        return candidate
            except OSError:
                continue

    return None


def _find_known_app_exe(app: dict) -> str | None:
    """Resolve a fallback Windows/UWP shortcut without doing another discovery pass."""
    if app.get("uwp"):
        return f"uwp:{app['uwp']}"

    for p in app.get("paths", []):
        if os.path.isfile(p):
            return p
    for exe_name in app.get("exe", []):
        found = shutil.which(exe_name)
        if found:
            return found
        found = _find_app_paths_registry(exe_name)
        if found:
            return found

    return None


def _find_app_exe(app_key: str) -> str | None:
    """
    Tìm file thực thi của app trên hệ thống.
    Ưu tiên catalog quét được; KNOWN_APPS chỉ là fallback cho shortcut Windows/UWP.
    """
    discovered = _get_discovered_app_by_key(app_key)
    if discovered:
        return discovered.get("exe_path")

    discovered_key, _, discovered_path = _find_discovered_app_key(app_key)
    if discovered_key and discovered_path:
        return discovered_path

    app = KNOWN_APPS.get(app_key)
    if not app:
        return None

    return _find_known_app_exe(app)


def resolve_app_name(user_input: str) -> tuple[str | None, str]:
    """
    Resolve tên app từ câu nói của user.
    Tầng 1: catalog quét được từ Registry + Start Menu.
    Tầng 2: alias fallback cho shortcut Windows/UWP.
    Returns: (app_key, display_name)
    """
    text = _clean_app_query(user_input)

    discovered_key, discovered_display, discovered_path = _find_discovered_app_key(text)
    if discovered_key:
        logger.info(
            "[SYS_EXEC] Resolved scanned app: '%s' -> %s (%s)",
            text,
            discovered_display,
            discovered_path,
        )
        return discovered_key, discovered_display

    for alias, key in sorted(APP_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in text:
            display = KNOWN_APPS[key]["display"]
            return key, display

    return None, user_input


# ══════════════════════════════════════════════════════════════
# Executor Functions
# ══════════════════════════════════════════════════════════════

def open_app(app_key: str) -> tuple[bool, str]:
    """Mở ứng dụng trên máy tính."""
    discovered = _get_discovered_app_by_key(app_key)
    if discovered:
        display = discovered["display"]
        exe_path = discovered.get("exe_path")
        if not exe_path:
            return False, f"Không tìm thấy đường dẫn mở {display}."
        try:
            subprocess.Popen([exe_path], shell=False)
            logger.info("[SYS_EXEC] Opened scanned app: %s (%s)", display, exe_path)
            return True, f"Đã mở {display}."
        except Exception as e:
            logger.error("[SYS_EXEC] Failed to open scanned app %s: %s", display, str(e)[:200])
            return False, f"Không thể mở {display}: {str(e)[:100]}"

    if not app_key.startswith("disc:"):
        discovered_key, _, _ = _find_discovered_app_key(app_key)
        if discovered_key:
            ok, msg = open_app(discovered_key)
            if ok or app_key not in KNOWN_APPS:
                return ok, msg

    app = KNOWN_APPS.get(app_key)
    if not app:
        return False, f"Không tìm thấy ứng dụng: {app_key}"

    display = app["display"]
    exe_path = _find_known_app_exe(app)

    if not exe_path:
        if os.name == "nt":
            for exe_name in app.get("exe", []):
                try:
                    os.startfile(exe_name)
                    logger.info("[SYS_EXEC] Opened app via ShellExecute: %s (%s)", display, exe_name)
                    return True, f"Đã mở {display}."
                except OSError:
                    continue
                except Exception as e:
                    logger.debug("[SYS_EXEC] ShellExecute fallback failed for %s: %s", exe_name, str(e)[:120])
        return False, f"Không tìm thấy {display} trên máy tính. Có thể chưa cài đặt."

    try:
        if exe_path.startswith("uwp:"):
            # UWP / Windows Store app
            uwp_uri = exe_path[4:]
            os.startfile(uwp_uri)
            logger.info("[SYS_EXEC] Opened UWP app: %s (%s)", display, uwp_uri)
            return True, f"Đã mở {display}."
        else:
            subprocess.Popen([exe_path], shell=False)
            logger.info("[SYS_EXEC] Opened app: %s (%s)", display, exe_path)
            return True, f"Đã mở {display}."
    except Exception as e:
        logger.error("[SYS_EXEC] Failed to open %s: %s", display, str(e)[:200])
        return False, f"Không thể mở {display}: {str(e)[:100]}"


def open_url_default_browser(url: str) -> tuple[bool, str]:
    """Mở URL bằng trình duyệt MẶC ĐỊNH (không chỉ Chrome)."""
    try:
        webbrowser.open(url)
        logger.info("[SYS_EXEC] Opened URL in default browser: %s", url[:100])
        return True, f"Đã mở trong trình duyệt mặc định."
    except Exception as e:
        logger.error("[SYS_EXEC] Failed to open URL: %s", str(e)[:200])
        return False, f"Không thể mở URL: {str(e)[:100]}"
