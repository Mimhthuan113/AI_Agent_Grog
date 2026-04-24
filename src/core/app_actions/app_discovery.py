"""
App Discovery — Tự động quét ứng dụng đã cài trên Windows
============================================================
KHÔNG hardcode path — Quét 3 nguồn:
1. Windows Registry (Uninstall keys)
2. Start Menu shortcuts (.lnk files)
3. PATH environment variable

Kết quả cache lại, lazy-load khi cần.
"""
from __future__ import annotations

import os
import sys
import logging
import subprocess
import struct
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# Quét Windows Registry
# ═══════════════════════════════════════════════════════════

def _scan_registry() -> dict[str, dict]:
    """Quét registry để tìm tất cả app đã cài."""
    apps = {}
    if sys.platform != "win32":
        return apps

    try:
        import winreg
    except ImportError:
        logger.warning("[DISCOVERY] winreg not available")
        return apps

    # Registry paths chứa thông tin uninstall
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except FileNotFoundError:
                        i += 1
                        continue

                    # Lấy exe path
                    exe_path = None
                    for field in ["DisplayIcon", "InstallLocation"]:
                        try:
                            val = winreg.QueryValueEx(subkey, field)[0]
                            if val:
                                # DisplayIcon thường có format: "path.exe,0"
                                clean = val.split(",")[0].strip().strip('"')
                                if clean.lower().endswith(".exe") and os.path.isfile(clean):
                                    exe_path = clean
                                    break
                                elif os.path.isdir(clean):
                                    # InstallLocation → tìm exe trong đó
                                    for f in Path(clean).glob("*.exe"):
                                        if f.name.lower() not in ("uninstall.exe", "uninst.exe", "unins000.exe"):
                                            exe_path = str(f)
                                            break
                        except (FileNotFoundError, OSError):
                            pass

                    if name and exe_path:
                        safe_key = name.lower().strip()
                        apps[safe_key] = {
                            "display": name,
                            "exe_path": exe_path,
                            "source": "registry",
                        }

                    winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except OSError:
            pass

    logger.info("[DISCOVERY] Registry scan: %d apps found", len(apps))
    return apps


# ═══════════════════════════════════════════════════════════
# Quét Start Menu shortcuts
# ═══════════════════════════════════════════════════════════

def _resolve_lnk(lnk_path: str) -> str | None:
    """Giải nén target path từ .lnk shortcut (pure Python, no COM)."""
    try:
        with open(lnk_path, "rb") as f:
            content = f.read()

        # LNK format header check
        if len(content) < 76:
            return None

        # Flags at offset 0x14
        flags = struct.unpack_from("<I", content, 0x14)[0]
        has_link_target = flags & 0x01
        has_link_info = flags & 0x02

        pos = 0x4C  # Start of Shell Link Target

        # Skip Shell Link Target ID List
        if has_link_target:
            list_size = struct.unpack_from("<H", content, pos)[0]
            pos += 2 + list_size

        # Parse Link Info
        if has_link_info:
            link_info_size = struct.unpack_from("<I", content, pos)[0]
            link_info_header_size = struct.unpack_from("<I", content, pos + 4)[0]

            # Local base path offset
            local_base_path_offset = struct.unpack_from("<I", content, pos + 16)[0]
            if local_base_path_offset > 0:
                path_start = pos + local_base_path_offset
                path_end = content.index(b'\x00', path_start)
                target = content[path_start:path_end].decode('mbcs', errors='ignore')
                if target and os.path.isfile(target):
                    return target

    except Exception:
        pass
    return None


def _scan_start_menu() -> dict[str, dict]:
    """Quét Start Menu để tìm shortcuts."""
    apps = {}

    start_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]

    for start_dir in start_dirs:
        if not os.path.isdir(start_dir):
            continue

        for lnk_file in Path(start_dir).rglob("*.lnk"):
            try:
                name = lnk_file.stem  # Tên shortcut (không có .lnk)
                target = _resolve_lnk(str(lnk_file))

                if target and target.lower().endswith(".exe"):
                    safe_key = name.lower().strip()
                    # Bỏ qua uninstall shortcuts
                    if any(skip in safe_key for skip in ["uninstall", "uninst", "remove", "gỡ cài"]):
                        continue
                    apps[safe_key] = {
                        "display": name,
                        "exe_path": target,
                        "source": "start_menu",
                    }
            except Exception:
                pass

    logger.info("[DISCOVERY] Start Menu scan: %d apps found", len(apps))
    return apps


# ═══════════════════════════════════════════════════════════
# Merged App Database (cached)
# ═══════════════════════════════════════════════════════════

_discovered_apps: dict[str, dict] | None = None


def get_discovered_apps() -> dict[str, dict]:
    """Lấy danh sách app đã phát hiện trên hệ thống (cached)."""
    global _discovered_apps
    if _discovered_apps is None:
        _discovered_apps = {}
        _discovered_apps.update(_scan_registry())
        _discovered_apps.update(_scan_start_menu())
        logger.info("[DISCOVERY] Total unique apps: %d", len(_discovered_apps))
    return _discovered_apps


def search_installed_app(query: str) -> dict | None:
    """
    Tìm app đã cài trên máy bằng tên.
    Fuzzy match: 'cốc cốc' → 'Cốc Cốc Browser', 'zalo' → 'Zalo PC'
    """
    apps = get_discovered_apps()
    query_lower = query.lower().strip()

    # Exact match
    if query_lower in apps:
        return apps[query_lower]

    # Partial match — tìm app chứa query
    candidates = []
    for key, info in apps.items():
        if query_lower in key or query_lower in info["display"].lower():
            candidates.append(info)

    # Ưu tiên match ngắn nhất (gần nhất)
    if candidates:
        candidates.sort(key=lambda x: len(x["display"]))
        return candidates[0]

    return None


def list_all_apps() -> list[dict]:
    """Danh sách tất cả app đã phát hiện (cho API endpoint)."""
    apps = get_discovered_apps()
    return [
        {"name": info["display"], "path": info["exe_path"], "source": info["source"]}
        for info in sorted(apps.values(), key=lambda x: x["display"])
    ]
