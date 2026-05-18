"""
Generic Desktop UI Agent — Điều khiển BẤT KỲ app nào trên Windows
====================================================================
Dùng Vision LLM (Groq) để nhìn màn hình → quyết định thao tác tiếp theo.
Không hardcode riêng cho bất kỳ app nào.

Groq Vision models (free tier):
    llama-3.2-90b-vision-preview
    llama-3.2-11b-vision-preview

Cài: pip install pyautogui pyperclip pygetwindow Pillow
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from contextlib import contextmanager
from io import BytesIO
from typing import Optional

# Import lazy de tranh loi neu chua cai pyautogui
try:
    import pyautogui as _pag
    # TAT FAILSAFE NGAY TAI MODULE LOAD — da co overlay + nut Ngung lam co che dung rieng
    _pag.FAILSAFE = False
    _pag.PAUSE = 0.25
except Exception:
    pass

logger = logging.getLogger(__name__)

# ── Vision models — Groq 2025 (Llama 4 hỗ trợ image) ─────────
# llama-3.2-*-vision-preview đã bị decommission — dùng Llama 4
VISION_MODEL          = "meta-llama/llama-4-scout-17b-16e-instruct"
VISION_MODEL_FALLBACK = "meta-llama/llama-4-maverick-17b-128e-instruct"

# ── Agent config ──────────────────────────────────────────────
MAX_STEPS        = 15      # So buoc toi da
STEP_DELAY       = 1.0     # Giay cho sau moi action
SCREENSHOT_SCALE = 1.0     # Giu dung pixel man hinh de tranh lech/toa do bi clamp vao goc
AGENT_TIMEOUT    = 120     # Timeout tong toi da (giay)
NATIVE_OVERLAY_ENABLED = False  # Frontend da co nut dung; overlay fullscreen se chan agent click app that
FOCUS_GUARD_ENABLED = True      # Keo app dich ve foreground neu user Alt-Tab/click sang app khac
PHYSICAL_INPUT_LOCK_ENABLED = True  # Khoa input vat ly rat ngan trong luc click/paste/hotkey tren Windows

# ── Stop Signal — dừng UI Agent giữa chừng ────────────────────
# asyncio.Event shared giữa run_ui_agent() và stop endpoint.
_agent_lock: asyncio.Lock | None = None   # Ngan concurrent agents
_stop_event: asyncio.Event | None = None
_automation_running: bool = False


def _get_lock() -> asyncio.Lock:
    """Tao lock lazy trong event loop hien tai."""
    global _agent_lock
    if _agent_lock is None:
        _agent_lock = asyncio.Lock()
    return _agent_lock


def is_automation_running() -> bool:
    """Kiểm tra UI Agent có đang chạy không."""
    return _automation_running


def request_stop_automation() -> bool:
    """
    Yêu cầu dừng UI Agent.
    Returns True nếu đang có agent chạy, False nếu không.
    """
    global _stop_event
    if _stop_event and _automation_running:
        _stop_event.set()
        logger.info("[UI_AGENT] Người dùng yêu cầu dừng.")
        return True
    return False


# ── System Prompt — Generic UI Agent ─────────────────────────
SYSTEM_PROMPT = """Bạn là Generic Desktop UI Agent.

Nhiệm vụ của bạn là điều khiển giao diện máy tính dựa trên ảnh chụp màn hình hiện tại và yêu cầu của người dùng.

Bạn KHÔNG được hardcode riêng cho bất kỳ app nào.
Bạn phải suy luận giao diện bằng thị giác:
- ô tìm kiếm
- nút đăng nhập
- nút gửi
- ô nhập văn bản
- danh sách kết quả
- thanh địa chỉ
- menu
- tab
- nút play/pause
- nút lưu
- nút đóng

Bạn chỉ được đề xuất MỘT hành động tiếp theo mỗi lần.

NGUYÊN TẮC QUAN TRỌNG:
1. Không đoán bừa.
2. Không click nếu không chắc vị trí.
3. Không gửi tin nhắn, email, form, thanh toán, xóa file, đổi cài đặt hệ thống nếu chưa xác minh rõ.
4. Với hành động rủi ro như:
   - gửi tin nhắn
   - gửi email
   - đăng bài
   - thanh toán
   - xóa dữ liệu
   - đổi mật khẩu
   - đăng xuất
   - cài/xóa phần mềm
   phải dừng lại và yêu cầu xác nhận.
5. Với hành động an toàn như:
   - mở app
   - tìm kiếm
   - nhập nội dung
   - phát video
   - mở trang web
   có thể tự làm nếu đủ tự tin.
6. Sau mỗi hành động phải chụp màn hình lại để kiểm tra trạng thái mới.
7. Nếu không chắc chắn, trả về action "ask_user" hoặc "fail".
8. Khi nhập tiếng Việt, ưu tiên paste_text thay vì type_text.
   Với các chuỗi tên/nội dung đã được user cung cấp trong task, phải paste NGUYÊN VĂN,
   giữ dấu tiếng Việt, giữ khoảng trắng; không tự rút gọn, không bỏ dấu, không gộp tên với nội dung.
9. Không tự ý dùng thông tin nhạy cảm như mật khẩu, OTP, tài khoản ngân hàng.
10. Nếu task hoàn tất, trả về action "done".

CÁC ACTION HỢP LỆ:
- open_app
- click
- double_click
- paste_text
- type_text
- press_key
- hotkey
- scroll
- wait
- ask_user
- done
- fail

QUY ƯỚC TỌA ĐỘ:
- Với click/double_click/scroll có x/y, x/y là pixel của ảnh screenshot đang nhìn.
- Gốc tọa độ (0,0) nằm ở góc trên-trái ảnh.
- Không trả tọa độ đã scale lên màn hình thật, không dùng hệ 0..1000.

SCHEMA JSON BẮT BUỘC (chỉ trả JSON, không giải thích thêm):

{
  "screen_state": "mô tả ngắn màn hình hiện tại",
  "task_understanding": {
    "app": "app cần dùng hoặc unknown",
    "goal": "mục tiêu chính",
    "target": "đối tượng cần thao tác nếu có",
    "content": "nội dung cần nhập nếu có"
  },
  "next_goal": "mục tiêu nhỏ của bước tiếp theo",
  "next_action": {
    "type": "open_app | click | double_click | paste_text | type_text | press_key | hotkey | scroll | wait | ask_user | done | fail",
    "app_name": null,
    "x": null,
    "y": null,
    "text": null,
    "key": null,
    "hotkeys": [],
    "direction": null,
    "amount": null,
    "question": null
  },
  "verification": {
    "need_verify_after_action": true,
    "expected_result": "sau hành động này màn hình nên thay đổi như thế nào"
  },
  "safety": {
    "risk_level": "low | medium | high",
    "can_execute": true,
    "need_user_confirm": false,
    "reason": "lý do ngắn gọn"
  },
  "confidence": 0.85
}"""


# ═══════════════════════════════════════════════════════════════
# Utils
# ═══════════════════════════════════════════════════════════════

def _check_deps() -> Optional[str]:
    """Kiem tra thu vien bat buoc va cau hinh pyautogui an toan."""
    missing = []
    for lib in ("pyautogui", "pyperclip", "PIL", "pygetwindow"):
        try:
            __import__(lib if lib != "PIL" else "PIL.Image")
        except ImportError:
            missing.append("Pillow" if lib == "PIL" else lib)
    if missing:
        return f"Thieu: {', '.join(missing)}. Chay: pip install {' '.join(missing)}"

    # Cau hinh pyautogui
    try:
        import pyautogui
        # TAT failsafe:
        # - Da co overlay native + nut Ngung + ESC lam co che dung rieng
        # - failsafe goc man hinh gay crash khi user di chuot trong overlay
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.25   # delay ngan giua moi action
    except Exception:
        pass

    return None


def _take_screenshot() -> tuple[bytes, int, int, int, int]:
    """
    Chụp toàn màn hình.
    Returns (jpeg_bytes, screen_w, screen_h, image_w, image_h).
    screen_w/h là hệ tọa độ pyautogui dùng để click, image_w/h là ảnh gửi LLM.
    """
    import pyautogui
    from PIL import Image

    screen_w, screen_h = pyautogui.size()
    screenshot = pyautogui.screenshot()
    shot_w, shot_h = screenshot.size

    image_w = max(1, int(shot_w * SCREENSHOT_SCALE))
    image_h = max(1, int(shot_h * SCREENSHOT_SCALE))
    if (image_w, image_h) != (shot_w, shot_h):
        screenshot = screenshot.resize((image_w, image_h), Image.LANCZOS)

    buf = BytesIO()
    screenshot.save(buf, format="JPEG", quality=78)
    return buf.getvalue(), screen_w, screen_h, image_w, image_h


def _coord_number(value) -> float | None:
    """Parse toa do LLM tra ve, chap nhan int/float hoac chuoi co so."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group())
    return None


def _clamp_coord(value: float, max_val: int) -> int:
    """Giu toa do trong man hinh ma khong de tran thanh click goc bat ngo."""
    return max(0, min(int(round(value)), max_val - 1))


def _int_or_default(value, default: int) -> int:
    """Parse so nguyen tu output LLM, fallback neu model tra chuoi khong phai so."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _rotate_api_keys(api_keys: list[str], offset: int) -> list[str]:
    """Round-robin order for a single vision request without logging key values."""
    if not api_keys:
        return []
    start = offset % len(api_keys)
    return api_keys[start:] + api_keys[:start]


def _normalize_coord_pair(
    x_raw,
    y_raw,
    screen_w: int,
    screen_h: int,
    image_w: int,
    image_h: int,
) -> tuple[int | None, int | None, str]:
    """
    Chuyen toa do LLM ve he toa do pyautogui.

    LLM doi khi tra:
    - pixel cua anh da gui,
    - pixel man hinh that,
    - ty le 0..1,
    - hoac he 0..1000.
    Ham nay xu ly cac dang do va tu choi toa do qua xa de tranh bi clamp vao mot goc.
    """
    x_val = _coord_number(x_raw)
    y_val = _coord_number(y_raw)
    if x_val is None or y_val is None:
        return None, None, "missing"

    if x_val < 0 or y_val < 0:
        return None, None, "negative"

    if 0 <= x_val <= 1 and 0 <= y_val <= 1:
        return (
            _clamp_coord(x_val * screen_w, screen_w),
            _clamp_coord(y_val * screen_h, screen_h),
            "normalized_0_1",
        )

    if (
        0 <= x_val <= 1000
        and 0 <= y_val <= 1000
        and (x_val > max(image_w, screen_w) or y_val > max(image_h, screen_h))
    ):
        return (
            _clamp_coord((x_val / 1000.0) * screen_w, screen_w),
            _clamp_coord((y_val / 1000.0) * screen_h, screen_h),
            "normalized_0_1000",
        )

    if x_val > max(image_w, screen_w) * 1.1 or y_val > max(image_h, screen_h) * 1.1:
        return None, None, "out_of_bounds"

    # Neu toa do nam ngoai anh da gui nhung van nam trong man hinh, xem nhu pixel man hinh that.
    if (
        (x_val > image_w or y_val > image_h)
        and x_val < screen_w
        and y_val < screen_h
    ):
        return _clamp_coord(x_val, screen_w), _clamp_coord(y_val, screen_h), "screen_px"

    # Mac dinh: toa do theo pixel cua anh gui cho LLM.
    x = (x_val / max(1, image_w)) * screen_w
    y = (y_val / max(1, image_h)) * screen_h
    return _clamp_coord(x, screen_w), _clamp_coord(y, screen_h), "image_px"


def _target_window_keywords(app_name: str | None) -> list[str]:
    """Các chuỗi dùng để nhận diện cửa sổ app đích."""
    if not app_name:
        return []

    raw = app_name.strip().lower()
    if not raw:
        return []

    keywords = {raw}
    try:
        from src.core.app_actions.system_executor import get_app_display_name, resolve_app_name

        app_key, display = resolve_app_name(raw)
        if app_key:
            key_text = app_key[5:] if app_key.startswith("disc:") else app_key
            keywords.add(key_text.replace("_", " ").lower())
            keywords.add(get_app_display_name(app_key).lower())
        if display:
            keywords.add(display.lower())
    except Exception:
        pass

    return [k for k in keywords if k]


def _target_process_names(app_name: str | None) -> list[str]:
    """Executable names used to recognize target app windows."""
    if not app_name:
        return []

    raw = app_name.strip().lower()
    names: set[str] = set()

    try:
        from src.core.app_actions.system_executor import KNOWN_APPS, _find_app_exe, resolve_app_name

        app_key, _ = resolve_app_name(raw)
        exe_path = _find_app_exe(app_key or raw)
        if exe_path and not exe_path.startswith("uwp:"):
            exe = str(exe_path).replace("/", "\\").rsplit("\\", 1)[-1].lower()
            if exe:
                names.add(exe)

        app = KNOWN_APPS.get(app_key or "")
        if app:
            for exe_name in app.get("exe", []):
                exe = str(exe_name).replace("/", "\\").rsplit("\\", 1)[-1].lower()
                if exe:
                    names.add(exe)
    except Exception:
        pass

    return [n for n in names if n]


def _window_pid(window) -> int | None:
    """Return process id for a pygetwindow window when available."""
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = (
            getattr(window, "_hWnd", None)
            or getattr(window, "_hwnd", None)
            or getattr(window, "hWnd", None)
        )
        if not hwnd:
            return None
        ctypes.windll.user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        ctypes.windll.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(int(hwnd), ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def _process_name_for_pid(pid: int) -> str:
    """Best-effort process image name without adding psutil as a dependency."""
    if not pid:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            handle = kernel32.OpenProcess(0x0400 | 0x0010, False, int(pid))  # QUERY_INFORMATION | VM_READ
        if not handle:
            return ""

        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            query_full = getattr(kernel32, "QueryFullProcessImageNameW", None)
            if query_full:
                query_full.argtypes = [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.LPWSTR,
                    ctypes.POINTER(wintypes.DWORD),
                ]
                query_full.restype = wintypes.BOOL
            if query_full and query_full(handle, 0, buf, ctypes.byref(size)):
                return buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()

            try:
                psapi = ctypes.windll.psapi
                if psapi.GetModuleBaseNameW(handle, None, buf, len(buf)):
                    return buf.value.lower()
            except Exception:
                return ""
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""

    return ""


def _window_process_name(window, cache: dict[int, str]) -> str:
    pid = _window_pid(window)
    if not pid:
        return ""
    if pid not in cache:
        cache[pid] = _process_name_for_pid(pid)
    return cache[pid]


def _window_matches_target(
    window,
    app_name: str | None,
    keywords: list[str] | None = None,
    process_names: list[str] | None = None,
    process_cache: dict[int, str] | None = None,
) -> tuple[bool, str]:
    """Match a window by title first, then by owning process name."""
    title = getattr(window, "title", "") if window else ""
    title_lower = (title or "").lower()
    keywords = keywords if keywords is not None else _target_window_keywords(app_name)

    if title_lower and any(keyword in title_lower for keyword in keywords):
        return True, f"title='{title}'"

    process_names = process_names if process_names is not None else _target_process_names(app_name)
    if process_names:
        process_cache = process_cache if process_cache is not None else {}
        process_name = _window_process_name(window, process_cache)
        if process_name and process_name.lower() in process_names:
            return True, f"process='{process_name}' title='{title}'"

    return False, title or ""


def _window_title_matches_target(title: str, app_name: str | None) -> bool:
    """Kiểm tra title cửa sổ có phải app đích không."""
    title_lower = (title or "").lower()
    if not title_lower:
        return False
    return any(keyword in title_lower for keyword in _target_window_keywords(app_name))


def _is_target_app_active(app_name: str | None) -> tuple[bool, str]:
    """Chỉ kiểm tra active window, không tự activate lại."""
    if not app_name or not FOCUS_GUARD_ENABLED:
        return True, "focus guard disabled"
    try:
        import pygetwindow as gw

        active = gw.getActiveWindow()
        keywords = _target_window_keywords(app_name)
        process_names = _target_process_names(app_name)
        matched, detail = _window_matches_target(
            active,
            app_name,
            keywords=keywords,
            process_names=process_names,
            process_cache={},
        )
        return matched, detail
    except Exception as exc:
        return True, f"active check unavailable: {exc}"


def _activate_window(window) -> bool:
    """Đưa một cửa sổ pygetwindow ra foreground."""
    try:
        if getattr(window, "isMinimized", False):
            window.restore()
            time.sleep(0.2)
        window.activate()
        time.sleep(0.25)
        return True
    except Exception as exc:
        logger.debug("[UI_AGENT] activate window failed: %s", str(exc)[:120])
        try:
            window.restore()
            time.sleep(0.15)
            window.activate()
            time.sleep(0.25)
            return True
        except Exception as exc2:
            logger.debug("[UI_AGENT] activate retry failed: %s", str(exc2)[:120])
    return False


def _ensure_target_app_focus(app_name: str | None, reopen_if_missing: bool = False) -> tuple[bool, str]:
    """
    Giữ app đích ở foreground.
    Nếu user Alt-Tab/click sang app khác, agent tự kéo app đích về trước khi chụp/click.
    """
    if not app_name or not FOCUS_GUARD_ENABLED:
        return True, "focus guard disabled"

    try:
        import pygetwindow as gw
    except Exception as exc:
        return True, f"pygetwindow unavailable: {exc}"

    try:
        keywords = _target_window_keywords(app_name)
        process_names = _target_process_names(app_name)
        process_cache: dict[int, str] = {}

        active = gw.getActiveWindow()
        active_title = getattr(active, "title", "") if active else ""
        active_matches, active_detail = _window_matches_target(
            active,
            app_name,
            keywords=keywords,
            process_names=process_names,
            process_cache=process_cache,
        )
        if active_matches:
            return True, f"already active: {active_detail}"

        candidates = []
        for window in gw.getAllWindows():
            title = getattr(window, "title", "") or ""
            width = max(0, getattr(window, "width", 0))
            height = max(0, getattr(window, "height", 0))
            if not title.strip() and (width == 0 or height == 0):
                continue
            matched, _ = _window_matches_target(
                window,
                app_name,
                keywords=keywords,
                process_names=process_names,
                process_cache=process_cache,
            )
            if matched:
                candidates.append(window)

        candidates.sort(
            key=lambda w: (
                bool(getattr(w, "isMinimized", False)),
                -max(0, getattr(w, "width", 0)) * max(0, getattr(w, "height", 0)),
            )
        )

        for window in candidates:
            title = getattr(window, "title", "") or app_name
            if _activate_window(window):
                return True, f"activated: {title}"

        if reopen_if_missing:
            from src.core.app_actions.system_executor import open_app, resolve_app_name

            app_key, display = resolve_app_name(app_name)
            if app_key:
                ok, msg = open_app(app_key)
                if ok:
                    time.sleep(2.0)
                    return _ensure_target_app_focus(app_name, reopen_if_missing=False)
                return False, msg
            return False, f"không tìm thấy app {app_name}"

        return False, f"không thấy cửa sổ {app_name}; active='{active_title}'"
    except Exception as exc:
        return False, f"focus guard lỗi: {str(exc)[:120]}"


def _set_physical_input_blocked(blocked: bool) -> bool:
    """Windows BlockInput; fail thì bỏ qua để tránh làm hỏng automation."""
    try:
        import ctypes

        ok = ctypes.windll.user32.BlockInput(bool(blocked))
        return bool(ok)
    except Exception as exc:
        logger.debug("[UI_AGENT] BlockInput unavailable: %s", str(exc)[:100])
        return False


@contextmanager
def _physical_input_lock(enabled: bool):
    """Khóa input người dùng cực ngắn trong lúc agent đang bấm/gõ để tránh Alt-Tab chen ngang."""
    locked = False
    try:
        if enabled and PHYSICAL_INPUT_LOCK_ENABLED:
            locked = _set_physical_input_blocked(True)
            if locked:
                logger.debug("[UI_AGENT] Physical input locked for action.")
        yield
    finally:
        if locked:
            _set_physical_input_blocked(False)
            logger.debug("[UI_AGENT] Physical input unlocked.")


def _action_needs_input_lock(action_type: str) -> bool:
    return action_type in {
        "click",
        "double_click",
        "paste_text",
        "type_text",
        "press_key",
        "hotkey",
        "scroll",
    }


# ═══════════════════════════════════════════════════════════════
# Vision LLM Call
# ═══════════════════════════════════════════════════════════════

async def _call_vision_llm(
    screenshot_bytes: bytes,
    screen_w: int,
    screen_h: int,
    image_w: int,
    image_h: int,
    user_task: str,
    current_state: str,
    memory: list[str],
    api_keys: list[str],
) -> dict:
    """
    Gửi screenshot → Groq Vision LLM → nhận JSON schema.
    Template prompt dùng placeholders {user_task}, {current_state}, {memory}.
    """
    import httpx

    img_b64 = base64.b64encode(screenshot_bytes).decode()
    memory_text = "\n".join(f"- {m}" for m in memory) if memory else "Chưa có"

    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
        },
        {
            "type": "text",
            "text": (
                f"User task: {user_task}\n"
                f"Current state: {current_state}\n"
                f"Ảnh bạn đang xem có kích thước {image_w}x{image_h}px. "
                f"Màn hình thật dùng để click là {screen_w}x{screen_h}px.\n"
                "Nếu action cần x/y, hãy trả x/y theo pixel của ẢNH bạn đang xem, "
                "gốc (0,0) ở góc trên-trái ảnh. Không dùng hệ 0..1000 và không tự phóng tọa độ.\n"
                "Bỏ qua mọi cửa sổ trạng thái/overlay của Aisha nếu có; chỉ thao tác trên app/trang chính.\n"
                f"Memory/context trước đó:\n{memory_text}\n\n"
                "Phân tích ảnh màn hình và trả về JSON đúng schema."
            ),
        },
    ]

    async with httpx.AsyncClient(timeout=40.0) as client:
        for model in [VISION_MODEL, VISION_MODEL_FALLBACK]:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content},
                ],
                "max_tokens": 600,
                "temperature": 0.0,
            }
            for key_index, api_key in enumerate(api_keys, start=1):
                try:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    data = resp.json()

                    # Kiểm tra lỗi API
                    if "error" in data:
                        err_msg = data["error"].get("message", str(data["error"]))
                        logger.warning(
                            "[UI_AGENT] Model %s key#%d error: %s — thử key/model tiếp theo",
                            model, key_index, err_msg[:120],
                        )
                        continue

                    if "choices" not in data or not data["choices"]:
                        logger.warning("[UI_AGENT] Model %s key#%d: no choices", model, key_index)
                        continue

                    raw = data["choices"][0]["message"]["content"].strip()
                    logger.debug("[UI_AGENT] LLM raw: %s", raw[:300])

                    # Extract JSON
                    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())

                    logger.warning("[UI_AGENT] Không parse được JSON từ: %s", raw[:100])
                    continue

                except json.JSONDecodeError as e:
                    logger.error("[UI_AGENT] JSON parse error: %s", e)
                    continue
                except Exception as e:
                    logger.error("[UI_AGENT] HTTP error (%s key#%d): %s", model, key_index, str(e)[:150])
                    continue

    return {
        "next_action": {"type": "fail"},
        "safety": {"can_execute": False},
        "screen_state": "Không thể gọi Vision LLM",
    }


# ═══════════════════════════════════════════════════════════════
# Action Executor
# ═══════════════════════════════════════════════════════════════

def _execute_action(
    action_dict: dict,
    screen_w: int,
    screen_h: int,
    image_w: int,
    image_h: int,
    target_app: str | None = None,
) -> str:
    """
    Thực thi 1 action từ JSON schema LLM trả về.
    Hỗ trợ tất cả action types trong schema người dùng định nghĩa.
    Returns: mô tả ngắn thao tác vừa làm.
    """
    import pyautogui

    # TAT FAILSAFE — da co overlay + nut Ngung lam co che dung rieng
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.15

    action_type = action_dict.get("type", "")
    x_raw = action_dict.get("x")
    y_raw = action_dict.get("y")
    text = action_dict.get("text") or ""
    key  = action_dict.get("key") or ""
    hotkeys = action_dict.get("hotkeys") or []
    direction = action_dict.get("direction") or "down"
    amount = _int_or_default(action_dict.get("amount"), 3)
    app_name = action_dict.get("app_name") or ""

    x, y, coord_space = _normalize_coord_pair(x_raw, y_raw, screen_w, screen_h, image_w, image_h)

    if action_type == "open_app":
        # Mở app qua system_executor (đã có auto-discovery)
        from src.core.app_actions.system_executor import open_app, resolve_app_name
        app_key, display = resolve_app_name(app_name)
        if app_key:
            ok, msg = open_app(app_key)
            # Chờ app khởi động
            time.sleep(3.0)
            return f"open_app '{display}': {'OK' if ok else msg}"
        return f"open_app '{app_name}': không tìm thấy"

    if action_type in ("done", "fail", "ask_user"):
        return f"[TERMINAL] {action_type}"

    if target_app and action_type != "wait":
        focused, detail = _ensure_target_app_focus(target_app, reopen_if_missing=True)
        if not focused:
            raise RuntimeError(f"Không giữ được cửa sổ {target_app} ở foreground: {detail}")

    with _physical_input_lock(_action_needs_input_lock(action_type)):
        return _execute_action_on_focused_window(
            action_type=action_type,
            x=x,
            y=y,
            coord_space=coord_space,
            text=text,
            key=key,
            hotkeys=hotkeys,
            direction=direction,
            amount=amount,
        )

    return f"unknown action: {action_type}"


def _execute_action_on_focused_window(
    *,
    action_type: str,
    x: int | None,
    y: int | None,
    coord_space: str,
    text: str,
    key: str,
    hotkeys: list,
    direction: str,
    amount: int,
) -> str:
    """Thực thi action sau khi focus guard đã đưa app đích ra foreground."""
    import pyautogui
    import pyperclip

    if action_type == "click":
        if x is None or y is None:
            return f"click: tọa độ không hợp lệ ({coord_space})"
        pyautogui.click(x, y)
        return f"click ({x}, {y}) từ {coord_space}"

    elif action_type == "double_click":
        if x is None or y is None:
            return f"double_click: tọa độ không hợp lệ ({coord_space})"
        pyautogui.doubleClick(x, y)
        return f"double_click ({x}, {y}) từ {coord_space}"

    elif action_type == "paste_text":
        # Ưu tiên paste qua clipboard — tốt nhất cho tiếng Việt
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        return f"paste_text: '{text[:40]}'"

    elif action_type == "type_text":
        # Gõ từng ký tự — chỉ dùng khi text toàn ASCII
        pyautogui.write(text, interval=0.04)
        return f"type_text: '{text[:40]}'"

    elif action_type == "press_key":
        pyautogui.press(key)
        return f"press_key: {key}"

    elif action_type == "hotkey":
        if hotkeys:
            pyautogui.hotkey(*hotkeys)
            return f"hotkey: {'+'.join(hotkeys)}"
        return "hotkey: danh sách rỗng"

    elif action_type == "scroll":
        clicks = -abs(amount) if direction == "down" else abs(amount)
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        return f"scroll {direction} {amount} tại ({x}, {y}) từ {coord_space}"

    elif action_type == "wait":
        secs = min(float(amount or 2), 10.0)
        time.sleep(secs)
        return f"wait {secs}s"

    return f"unknown action: {action_type}"


# ═══════════════════════════════════════════════════════════════
# Native Windows Overlay (tkinter) — khoa toan man hinh
# ═══════════════════════════════════════════════════════════════

_overlay_thread = None
_overlay_root = None


def _run_native_overlay():
    """
    Chay trong thread rieng: hien thi cua so trang thai nho always-on-top.
    Khong dung fullscreen vi se che screenshot va chan pyautogui click app that.
    """
    global _overlay_root
    try:
        import tkinter as tk

        root = tk.Tk()
        _overlay_root = root

        width, height = 290, 104
        screen_w = root.winfo_screenwidth()
        x = max(16, screen_w - width - 24)
        y = 24

        root.geometry(f"{width}x{height}+{x}+{y}")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)
        root.configure(bg="#0a0818")
        root.overrideredirect(True)

        bg = tk.Frame(root, bg="#0a0818")
        bg.place(relx=0, rely=0, relwidth=1, relheight=1)

        box = tk.Frame(
            root,
            bg="#1a1535",
            highlightbackground="#7c5cff",
            highlightthickness=2,
            bd=0,
        )
        box.place(relx=0, rely=0, relwidth=1, relheight=1)

        lbl_spinner = tk.Label(
            box, text="⟳", font=("Segoe UI", 22), fg="#7c5cff", bg="#1a1535"
        )
        lbl_spinner.place(x=18, y=14, width=40, height=40)

        def _spin(angle=0):
            chars = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
            lbl_spinner.config(text=chars[angle % len(chars)])
            if _overlay_root:
                root.after(100, _spin, angle + 1)

        _spin()

        tk.Label(
            box,
            text="Dang tu dong hoa",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff", bg="#1a1535",
        ).place(x=64, y=14)

        tk.Label(
            box,
            text="Co the bam Ngung tren day hoac trong app.",
            font=("Segoe UI", 9),
            fg="#a0a0c0", bg="#1a1535",
        ).place(x=64, y=39)

        def _on_stop():
            request_stop_automation()
            _close_native_overlay()

        stop_btn = tk.Button(
            box,
            text="Ngung",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#e03a3a",
            activebackground="#ff4f4f",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=18,
            pady=6,
            cursor="hand2",
            command=_on_stop,
        )
        stop_btn.place(x=196, y=64, width=76, height=28)

        # ESC = Ngung
        root.bind("<Escape>", lambda e: _on_stop())
        # Ngan tat ca phim khac (tuy khong block system-level)
        root.bind("<Key>", lambda e: "break")

        root.mainloop()
    except Exception as exc:
        logger.error("[UI_AGENT] Overlay error: %s", exc)
    finally:
        _overlay_root = None


def _open_native_overlay():
    """Mo overlay trong daemon thread."""
    global _overlay_thread
    import threading
    _overlay_thread = threading.Thread(target=_run_native_overlay, daemon=True)
    _overlay_thread.start()


def _close_native_overlay():
    """Dong overlay an toan tu bat ky thread nao."""
    global _overlay_root
    if _overlay_root:
        try:
            _overlay_root.after(0, _overlay_root.destroy)
        except Exception:
            pass
        _overlay_root = None


# ═══════════════════════════════════════════════════════════════
# Main Agent Loop
# ═══════════════════════════════════════════════════════════════

async def run_ui_agent(
    goal: str,
    app_to_open: str | None = None,
) -> tuple[bool, str, list[str]]:
    """
    Entry point: chay UI Agent voi mutex lock + timeout tong 120s.
    Nguoi dung co the dung qua request_stop_automation() / nut Ngung tren frontend.
    """
    from src.config import get_settings

    err = _check_deps()
    if err:
        return False, err, []

    settings = get_settings()
    api_keys = settings.groq_vision_api_key_list
    if not api_keys:
        return False, "Thiếu GROQ_API_KEY trong file .env.", []
    logger.info("[UI_AGENT] Vision key pool loaded: %d key(s)", len(api_keys))

    # Guard: chi cho phep 1 agent chay tai mot thoi diem
    lock = _get_lock()
    if lock.locked():
        return False, "Một tác vụ tự động hóa khác đang chạy. Vui lòng đợi.", []

    async with lock:
        try:
            return await asyncio.wait_for(
                _run_agent_core(goal, api_keys, app_to_open),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("[UI_AGENT] Quá thời gian %ds.", AGENT_TIMEOUT)
            request_stop_automation()
            return False, f"Tự động hóa quá thời gian ({AGENT_TIMEOUT}s). Đã dừng.", []
        finally:
            global _automation_running
            _automation_running = False
            _close_native_overlay()
            logger.info("[UI_AGENT] Kết thúc (đã giải phóng lock).")


async def _run_agent_core(
    goal: str,
    api_keys: list[str],
    app_to_open: str | None,
) -> tuple[bool, str, list[str]]:
    """Vòng lặp chính của agent (chạy bên trong lock + timeout)."""
    global _stop_event, _automation_running

    _stop_event = asyncio.Event()
    _automation_running = True
    logger.info("[UI_AGENT] Bắt đầu: goal='%s'", goal[:80])

    if NATIVE_OVERLAY_ENABLED:
        _open_native_overlay()

    try:
        # Mở app trước nếu cần
        if app_to_open:
            logger.info("[UI_AGENT] Mở app: %s", app_to_open)
            try:
                from src.core.app_actions.system_executor import open_app, resolve_app_name
                app_key, display = resolve_app_name(app_to_open)
                if app_key:
                    ok, msg = await asyncio.to_thread(open_app, app_key)
                    logger.info("[UI_AGENT] open_app '%s': %s", display, msg)
                    await asyncio.sleep(3.5)
                    focused, detail = await asyncio.to_thread(
                        _ensure_target_app_focus,
                        app_to_open,
                        True,
                    )
                    if focused:
                        logger.info("[UI_AGENT] Focus guard ready: %s", detail)
                    else:
                        logger.warning("[UI_AGENT] Focus guard chưa khóa được app: %s", detail)
                else:
                    logger.warning("[UI_AGENT] Không tìm thấy app: %s", app_to_open)
            except Exception as exc:
                logger.error("[UI_AGENT] Lỗi mở app: %s", exc)

        history: list[str] = []
        current_state = "Bắt đầu — chưa thực hiện bước nào"

        for step in range(MAX_STEPS):
            # Kiểm tra tín hiệu dừng trước mỗi bước
            if _stop_event.is_set():
                logger.info("[UI_AGENT] Đã dừng tại bước %d.", step + 1)
                return False, "Đã dừng theo yêu cầu của bạn.", history

            logger.info("[UI_AGENT] Bước %d/%d", step + 1, MAX_STEPS)

            if app_to_open:
                focused, detail = await asyncio.to_thread(
                    _ensure_target_app_focus,
                    app_to_open,
                    True,
                )
                if not focused:
                    logger.warning("[UI_AGENT] Focus guard failed: %s", detail)
                    return (
                        False,
                        f"Không thể giữ cửa sổ {app_to_open} ở trước màn hình. Đã dừng để tránh thao tác nhầm.",
                        history,
                    )

            # 1. Chụp màn hình
            try:
                screenshot_bytes, screen_w, screen_h, image_w, image_h = await asyncio.to_thread(_take_screenshot)
            except Exception as exc:
                return False, f"Không thể chụp màn hình: {exc}", history

            if app_to_open:
                active_ok, active_title = await asyncio.to_thread(_is_target_app_active, app_to_open)
                if not active_ok:
                    logger.warning(
                        "[UI_AGENT] User switched window during screenshot: active='%s'",
                        active_title,
                    )
                    history.append(
                        f"[{step+1}] focus_guard: cửa sổ đổi sang '{active_title[:50]}', chụp lại"
                    )
                    await asyncio.to_thread(_ensure_target_app_focus, app_to_open, True)
                    current_state = "User vừa chuyển cửa sổ; đã đưa app đích về lại và cần chụp lại."
                    continue

            # 2. Hỏi Vision LLM
            response = await _call_vision_llm(
                screenshot_bytes=screenshot_bytes,
                screen_w=screen_w,
                screen_h=screen_h,
                image_w=image_w,
                image_h=image_h,
                user_task=goal,
                current_state=current_state,
                memory=history[-6:],
                api_keys=_rotate_api_keys(api_keys, step),
            )

            next_action  = response.get("next_action", {})
            action_type  = next_action.get("type", "fail")
            safety       = response.get("safety", {})
            confidence   = float(response.get("confidence", 0.0))
            screen_state = response.get("screen_state", "")
            next_goal    = response.get("next_goal", "")

            logger.info("[UI_AGENT] action=%s conf=%.2f | %s",
                        action_type, confidence, screen_state[:60])

            # 3. Hành động kết thúc
            if action_type == "done":
                msg = next_action.get("text") or next_goal or "Hoàn thành!"
                return True, msg, history

            if action_type == "fail":
                msg = next_action.get("text") or "Không thể thực hiện yêu cầu."
                return False, msg, history

            if action_type == "ask_user":
                q = next_action.get("question") or "Cần thêm thông tin để tiếp tục."
                return False, f"⚠️ Aisha cần xác nhận: {q}", history

            # 4. Kiểm tra an toàn
            can_execute  = safety.get("can_execute", True)
            need_confirm = safety.get("need_user_confirm", False)
            risk         = safety.get("risk_level", "low")
            if not can_execute or (need_confirm and risk in ("medium", "high")):
                reason = safety.get("reason", "")
                return False, f"⚠️ Hành động cần xác nhận ({risk} risk): {reason}", history

            # 5. Thực thi action
            try:
                desc = await asyncio.to_thread(
                    _execute_action,
                    next_action,
                    screen_w,
                    screen_h,
                    image_w,
                    image_h,
                    app_to_open,
                )
                history.append(f"[{step+1}] {action_type}: {desc} | {screen_state[:50]}")
                current_state = f"Sau bước {step+1}: {next_goal or desc}"
                logger.info("[UI_AGENT] Thực thi xong: %s", desc)
            except Exception as exc:
                history.append(f"[{step+1}] Lỗi {action_type}: {exc}")
                logger.error("[UI_AGENT] Lỗi thực thi: %s", exc)
                return False, f"Lỗi khi thực thi '{action_type}': {exc}", history

            # 6. Chờ có thể bị ngắt bởi stop signal
            try:
                await asyncio.wait_for(asyncio.shield(_stop_event.wait()), timeout=STEP_DELAY)
                return False, "Đã dừng theo yêu cầu của bạn.", history
            except asyncio.TimeoutError:
                pass  # Bình thường — tiếp tục bước tiếp theo

        return False, f"Đã thử {MAX_STEPS} bước nhưng chưa hoàn thành mục tiêu.", history

    finally:
        if _stop_event:
            _stop_event.clear()
        _close_native_overlay()


# ═══════════════════════════════════════════════════════════════
# Wrapper tiện ích cho router
# ═══════════════════════════════════════════════════════════════

async def ui_agent_zalo_chat(
    contact_name: str,
    message: str,
    auto_send: bool = True,
) -> tuple[bool, str]:
    """Wrapper: Zalo tìm contact theo TÊN + soạn/gửi tin."""
    contact_name = " ".join(contact_name.split())
    message = " ".join(message.split())
    send_part = (
        "Chỉ sau khi đã mở đúng cửa sổ chat, paste EXACT_MESSAGE vào ô nhập tin nhắn "
        "rồi bấm Enter để gửi."
        if auto_send
        else "Chỉ sau khi đã mở đúng cửa sổ chat, paste EXACT_MESSAGE vào ô nhập tin nhắn "
             "nhưng KHÔNG bấm Enter."
    )
    goal = (
        f"Mở app Zalo trên Windows. "
        f"EXACT_CONTACT = {json.dumps(contact_name, ensure_ascii=False)}. "
        f"EXACT_MESSAGE = {json.dumps(message, ensure_ascii=False)}. "
        "Trong ô tìm kiếm của Zalo, CHỈ paste EXACT_CONTACT, không paste nội dung tin nhắn vào ô tìm kiếm. "
        "Nếu ô tìm kiếm đang có chữ sai hoặc dính nội dung tin nhắn, chọn toàn bộ rồi thay bằng đúng EXACT_CONTACT. "
        "Khi thấy kết quả liên hệ phù hợp EXACT_CONTACT, mở chat với người đó. "
        f"{send_part} "
        "Tuyệt đối không gộp EXACT_CONTACT và EXACT_MESSAGE trong cùng một lần paste."
    )
    ok, msg, _ = await run_ui_agent(
        goal=goal,
        app_to_open="zalo",
    )
    return ok, msg


async def ui_agent_generic(
    app_name: str,
    task_description: str,
) -> tuple[bool, str]:
    """
    Wrapper: Mở bất kỳ app nào + thực hiện task bất kỳ.

    Ví dụ:
        ui_agent_generic("word", "tạo file mới và gõ 'Hello World'")
        ui_agent_generic("chrome", "mở tab mới và tìm 'thời tiết hôm nay'")
        ui_agent_generic("teams", "nhắn cho Nguyễn An: họp lúc 3h")
    """
    try:
        from src.core.app_actions.system_executor import resolve_app_name

        app_key, display_name = resolve_app_name(app_name)
    except Exception:
        app_key, display_name = None, app_name

    display_name = display_name or app_name

    goal = (
        f"Mở ứng dụng {display_name} trên máy tính Windows. "
        f"Sau đó thực hiện: {task_description}."
    )
    ok, msg, _ = await run_ui_agent(
        goal=goal,
        app_to_open=display_name,
    )
    return ok, msg
