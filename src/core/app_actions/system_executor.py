"""
System Executor — Thực thi lệnh hệ thống trên máy tính
=========================================================
AI Agent THẬT SỰ — không chỉ mở URL trong browser.

Khả năng:
- Mở bất kỳ ứng dụng nào đã cài (Chrome, Cốc Cốc, Zalo, VS Code...)
- Mở file / folder bằng app mặc định
- Mở URL bằng trình duyệt MẶC ĐỊNH (không chỉ Chrome)
- Tìm kiếm trên YouTube, Google Maps... bằng trình duyệt mặc định
- Thực thi lệnh hệ thống (owner only)

Bảo mật: Chỉ owner mới có quyền — RBAC đã enforce ở agent.py
"""
from __future__ import annotations

import os
import sys
import logging
import subprocess
import webbrowser
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# App Registry — Mapping tên app → cách mở trên Windows
# ══════════════════════════════════════════════════════════════

# Registry: tên thường gọi → (exe_names, common_paths)
KNOWN_APPS: dict[str, dict] = {
    # Browsers
    "chrome": {
        "exe": ["chrome.exe"],
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "display": "Google Chrome",
    },
    "coccoc": {
        "exe": ["browser.exe"],
        "paths": [
            r"C:\Program Files\CocCoc\Browser\Application\browser.exe",
            r"C:\Program Files (x86)\CocCoc\Browser\Application\browser.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\CocCoc\Browser\Application\browser.exe"),
        ],
        "display": "Cốc Cốc",
    },
    "firefox": {
        "exe": ["firefox.exe"],
        "paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "display": "Firefox",
    },
    "edge": {
        "exe": ["msedge.exe"],
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "display": "Microsoft Edge",
    },
    # Communication
    "zalo": {
        "exe": ["Zalo.exe"],
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Zalo\Zalo.exe"),
            os.path.expandvars(r"%APPDATA%\Zalo\Zalo.exe"),
            r"C:\Program Files\Zalo\Zalo.exe",
            r"C:\Program Files (x86)\ZaloPC\Zalo.exe",
        ],
        "display": "Zalo",
    },
    "telegram": {
        "exe": ["Telegram.exe"],
        "paths": [
            os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
        ],
        "display": "Telegram",
    },
    # Office
    "word": {
        "exe": ["WINWORD.EXE"],
        "paths": [],
        "display": "Microsoft Word",
    },
    "excel": {
        "exe": ["EXCEL.EXE"],
        "paths": [],
        "display": "Microsoft Excel",
    },
    "powerpoint": {
        "exe": ["POWERPNT.EXE"],
        "paths": [],
        "display": "Microsoft PowerPoint",
    },
    # Dev tools
    "vscode": {
        "exe": ["Code.exe"],
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        ],
        "display": "Visual Studio Code",
    },
    "notepad": {
        "exe": ["notepad.exe"],
        "paths": [r"C:\Windows\System32\notepad.exe"],
        "display": "Notepad",
    },
    # Media
    "spotify": {
        "exe": ["Spotify.exe"],
        "paths": [
            os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        ],
        "display": "Spotify",
    },
    # System
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

# Alias mapping: từ người dùng nói → key trong KNOWN_APPS
APP_ALIASES: dict[str, str] = {
    # Chrome
    "google chrome": "chrome", "chrome": "chrome", "chome": "chrome",
    "trình duyệt": "chrome", "trinh duyet": "chrome", "browser": "chrome",
    # Cốc Cốc
    "cốc cốc": "coccoc", "coc coc": "coccoc", "coccoc": "coccoc",
    # Firefox
    "firefox": "firefox",
    # Edge
    "edge": "edge", "microsoft edge": "edge",
    # Zalo
    "zalo": "zalo", "zalo pc": "zalo",
    # Telegram
    "telegram": "telegram",
    # Office
    "word": "word", "microsoft word": "word",
    "excel": "excel", "microsoft excel": "excel",
    "powerpoint": "powerpoint", "ppt": "powerpoint",
    # Dev
    "vscode": "vscode", "vs code": "vscode", "visual studio code": "vscode",
    "notepad": "notepad", "note pad": "notepad",
    # Media
    "spotify": "spotify",
    # System
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


def _find_app_exe(app_key: str) -> str | None:
    """
    Tìm file thực thi của app trên hệ thống.
    3 tầng:
      1. UWP URI (Windows Store apps)
      2. Hardcoded paths + PATH scan (nhanh)
      3. Auto-discovery: quét Registry + Start Menu (chậm hơn, nhưng tìm được mọi thứ)
    """
    app = KNOWN_APPS.get(app_key)
    if not app:
        return None

    # Tầng 1: UWP
    if app.get("uwp"):
        return f"uwp:{app['uwp']}"

    # Tầng 2: Known paths + PATH
    for p in app.get("paths", []):
        if os.path.isfile(p):
            return p
    for exe_name in app.get("exe", []):
        found = shutil.which(exe_name)
        if found:
            return found

    # Tầng 3: Auto-discovery — quét Registry + Start Menu
    try:
        from src.core.app_actions.app_discovery import search_installed_app
        display = app.get("display", app_key)
        discovered = search_installed_app(display)
        if discovered:
            logger.info("[SYS_EXEC] Auto-discovered: %s → %s", display, discovered["exe_path"])
            return discovered["exe_path"]
    except Exception as e:
        logger.warning("[SYS_EXEC] Discovery fallback error: %s", str(e)[:100])

    return None


def resolve_app_name(user_input: str) -> tuple[str | None, str]:
    """
    Resolve tên app từ câu nói của user.
    Tầng 1: APP_ALIASES (hardcoded, nhanh)
    Tầng 2: Auto-discovery (quét máy, tìm mọi app)
    Returns: (app_key, display_name)
    """
    text = user_input.lower().strip()

    # Tầng 1: Alias cố định
    for alias, key in sorted(APP_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in text:
            display = KNOWN_APPS[key]["display"]
            return key, display

    # Tầng 2: Auto-discovery — tìm trên máy thật
    try:
        from src.core.app_actions.app_discovery import search_installed_app
        discovered = search_installed_app(text)
        if discovered:
            # Tạo dynamic key
            dyn_key = f"_discovered_{text.replace(' ', '_')}"
            # Cache vào KNOWN_APPS để lần sau nhanh hơn
            KNOWN_APPS[dyn_key] = {
                "exe": [],
                "paths": [discovered["exe_path"]],
                "display": discovered["display"],
            }
            logger.info("[SYS_EXEC] Discovered app: '%s' → %s (%s)", text, discovered["display"], discovered["exe_path"])
            return dyn_key, discovered["display"]
    except Exception as e:
        logger.warning("[SYS_EXEC] Discovery error: %s", str(e)[:100])

    return None, user_input


# ══════════════════════════════════════════════════════════════
# Executor Functions
# ══════════════════════════════════════════════════════════════

def open_app(app_key: str) -> tuple[bool, str]:
    """Mở ứng dụng trên máy tính."""
    app = KNOWN_APPS.get(app_key)
    if not app:
        return False, f"Không tìm thấy ứng dụng: {app_key}"

    display = app["display"]
    exe_path = _find_app_exe(app_key)

    if not exe_path:
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


def open_file_or_folder(path: str) -> tuple[bool, str]:
    """Mở file hoặc folder bằng app mặc định."""
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return False, f"Không tìm thấy: {path}"
        os.startfile(str(target))
        logger.info("[SYS_EXEC] Opened: %s", target)
        return True, f"Đã mở {target.name}."
    except Exception as e:
        logger.error("[SYS_EXEC] Failed: %s", str(e)[:200])
        return False, f"Không thể mở: {str(e)[:100]}"


def open_explorer(path: str = "") -> tuple[bool, str]:
    """Mở File Explorer (This PC hoặc folder cụ thể)."""
    try:
        if path:
            target = Path(path).expanduser().resolve()
            subprocess.Popen(["explorer", str(target)])
        else:
            subprocess.Popen(["explorer", "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"])  # This PC
        logger.info("[SYS_EXEC] Opened Explorer: %s", path or "This PC")
        return True, f"Đã mở {'thư mục ' + path if path else 'This PC'}."
    except Exception as e:
        return False, f"Không thể mở Explorer: {str(e)[:100]}"
