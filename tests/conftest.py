"""
Pytest conftest — Setup chung cho mọi test
==========================================
Tự động inject project root vào sys.path để các test có thể `from src...`
mà không cần `sys.path.insert(0, ".")` thủ công.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root = tests/../
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
