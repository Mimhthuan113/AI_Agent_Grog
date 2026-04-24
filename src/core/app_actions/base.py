"""
App Action — Base Provider
============================
Abstract base class cho tất cả app providers.
Mỗi provider đại diện 1 ứng dụng/dịch vụ trên điện thoại.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AppActionResult:
    """Kết quả thực thi app action."""
    success: bool
    message: str                        # Thông báo cho user (tiếng Việt)
    intent_uri: str | None = None       # Android Intent URI (deep link)
    data: dict | None = None            # Dữ liệu bổ sung (search results, etc.)
    provider: str = ""                  # Tên provider
    action: str = ""                    # Tên action


class AppProvider(ABC):
    """Base class cho app providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên provider (unique ID)."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Tên hiển thị cho user."""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """Emoji icon."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[dict]:
        """Danh sách actions provider có thể thực hiện."""
        ...

    @abstractmethod
    async def execute(self, action: str, params: dict) -> AppActionResult:
        """Thực thi action."""
        ...

    def can_handle(self, action: str) -> bool:
        """Kiểm tra provider có xử lý được action không."""
        return any(c["action"] == action for c in self.get_capabilities())
