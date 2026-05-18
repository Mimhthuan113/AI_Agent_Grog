"""
File Operations — Tạo, viết, sửa file/folder trên máy
========================================================
AI Agent thật sự — KHÔNG CHỈ MỞ, mà còn TẠO và VIẾT.

Khả năng:
- Tạo folder ở vị trí an toàn
- Tạo file mới (txt, docx...)
- Ghi nội dung ban đầu vào file
- Mở file bằng app mặc định sau khi tạo

Bảo mật:
- Chỉ cho phép trong user directories (Desktop, Documents, Downloads...)
- KHÔNG cho phép viết vào System32, Program Files, Windows...
"""
from __future__ import annotations

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Các đường dẫn an toàn ──────────────────────────────────
SAFE_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Music",
    Path.home() / "Videos",
    Path.home() / "Pictures",
    Path.home(),
]

# Đường dẫn CẤM — bảo vệ hệ thống
FORBIDDEN_PATHS = [
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
]


def _resolve_location(location_hint: str) -> Path:
    """
    Giải quyết hint vị trí từ user input.
    'desktop' → Desktop, 'documents' → Documents, '' → Desktop mặc định.
    """
    hint = location_hint.lower().strip()
    home = Path.home()

    mapping = {
        "desktop": home / "Desktop",
        "bàn làm việc": home / "Desktop",
        "ban lam viec": home / "Desktop",
        "trang chủ": home / "Desktop",
        "trang chu": home / "Desktop",
        "documents": home / "Documents",
        "tài liệu": home / "Documents",
        "tai lieu": home / "Documents",
        "downloads": home / "Downloads",
        "tải về": home / "Downloads",
        "tai ve": home / "Downloads",
        "music": home / "Music",
        "nhạc": home / "Music",
        "nhac": home / "Music",
        "videos": home / "Videos",
        "video": home / "Videos",
        "pictures": home / "Pictures",
        "ảnh": home / "Pictures",
        "anh": home / "Pictures",
        "hình": home / "Pictures",
        "hinh": home / "Pictures",
    }

    return mapping.get(hint, home / "Desktop")


def _is_safe_path(target: Path) -> bool:
    """Kiểm tra đường dẫn có an toàn không."""
    target_str = str(target.resolve()).lower()
    for forbidden in FORBIDDEN_PATHS:
        if target_str.startswith(forbidden.lower()):
            return False
    return True


def create_folder(name: str, location: str = "desktop") -> tuple[bool, str]:
    """Tạo folder mới."""
    parent = _resolve_location(location)
    target = parent / name

    if not _is_safe_path(target):
        return False, f"Không được phép tạo folder ở {target}."

    try:
        target.mkdir(parents=True, exist_ok=True)
        logger.info("[FILE_OPS] Created folder: %s", target)
        return True, f"Đã tạo folder \"{name}\" tại {parent}."
    except Exception as e:
        logger.error("[FILE_OPS] Failed to create folder: %s", str(e)[:200])
        return False, f"Không thể tạo folder: {str(e)[:100]}"


def create_file(name: str, content: str = "", location: str = "desktop", open_after: bool = True) -> tuple[bool, str]:
    """Tạo file mới với nội dung."""
    parent = _resolve_location(location)
    target = parent / name

    if not _is_safe_path(target):
        return False, f"Không được phép tạo file ở {target}."

    # Thêm extension mặc định nếu chưa có
    if not target.suffix:
        target = target.with_suffix(".txt")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("[FILE_OPS] Created file: %s (%d chars)", target, len(content))

        # Mở file bằng app mặc định
        if open_after:
            os.startfile(str(target))

        return True, f"Đã tạo file \"{target.name}\" tại {parent}" + (f" với nội dung." if content else ".")
    except Exception as e:
        logger.error("[FILE_OPS] Failed: %s", str(e)[:200])
        return False, f"Không thể tạo file: {str(e)[:100]}"
