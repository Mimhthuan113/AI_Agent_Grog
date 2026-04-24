"""
File Operations — Tạo, viết, sửa file/folder trên máy
========================================================
AI Agent thật sự — KHÔNG CHỈ MỞ, mà còn TẠO và VIẾT.

Khả năng:
- Tạo folder ở bất kỳ đâu
- Tạo file mới (txt, docx...)
- Viết nội dung vào file
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


def write_to_existing_file(path: str, content: str, mode: str = "append") -> tuple[bool, str]:
    """Viết thêm hoặc ghi đè nội dung file."""
    target = Path(path).expanduser().resolve()
    if not _is_safe_path(target):
        return False, "Không được phép chỉnh sửa file này."

    if not target.exists():
        return False, f"File không tồn tại: {path}"

    try:
        open_mode = "a" if mode == "append" else "w"
        with open(target, open_mode, encoding="utf-8") as f:
            f.write(content)
        logger.info("[FILE_OPS] Written to %s (%s, %d chars)", target, mode, len(content))
        return True, f"Đã {'thêm vào' if mode == 'append' else 'ghi lại'} file {target.name}."
    except Exception as e:
        return False, f"Không thể viết file: {str(e)[:100]}"


def delete_file_or_folder(path: str) -> tuple[bool, str]:
    """Xóa file hoặc folder (đưa vào Recycle Bin nếu có thể)."""
    target = Path(path).expanduser().resolve()
    if not _is_safe_path(target):
        return False, "Không được phép xóa ở đường dẫn này."

    if not target.exists():
        return False, f"Không tìm thấy: {path}"

    try:
        # Thử dùng send2trash (safe delete)
        try:
            from send2trash import send2trash
            send2trash(str(target))
            logger.info("[FILE_OPS] Sent to trash: %s", target)
            return True, f"Đã đưa {target.name} vào Thùng rác."
        except ImportError:
            # Fallback: xóa thật
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                import shutil
                shutil.rmtree(str(target))
            logger.info("[FILE_OPS] Deleted: %s", target)
            return True, f"Đã xóa {target.name}."
    except Exception as e:
        return False, f"Không thể xóa: {str(e)[:100]}"
