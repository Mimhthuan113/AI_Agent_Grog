"""
Vault — Secret Management Wrapper
====================================
Abstraction layer cho viec quan ly secrets.

MVP: EnvVault — doc tu environment variables (.env)
Production: HashiCorpVault hoac AWS Secrets Manager (Phase 2)

Nguyen tac:
- KHONG hardcode bat ky secret nao
- Moi secret duoc truy cap qua interface thong nhat
- Factory pattern de switch giua dev/prod
"""

from __future__ import annotations

import os
import logging
from typing import Protocol, runtime_checkable

from src.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class SecretVault(Protocol):
    """Interface chung cho tat ca vault implementations."""

    def get(self, key: str) -> str:
        """Lay gia tri secret theo key."""
        ...

    def get_or_default(self, key: str, default: str = "") -> str:
        """Lay secret hoac tra ve default."""
        ...


class EnvVault:
    """
    Dev Vault — doc secrets tu environment variables.
    Su dung trong development va MVP.
    """

    def get(self, key: str) -> str:
        """
        Lay secret tu env var.
        Raises ValueError neu khong tim thay.
        """
        value = os.environ.get(key, "")
        if not value:
            logger.error("[VAULT] Secret not found: %s", key)
            raise ValueError(f"Secret '{key}' not found in environment")
        # Log KHONG bao gio in gia tri secret
        logger.debug("[VAULT] Secret loaded: %s (length=%d)", key, len(value))
        return value

    def get_or_default(self, key: str, default: str = "") -> str:
        """Lay secret hoac tra ve default (khong raise)."""
        value = os.environ.get(key, default)
        return value


class InMemoryVault:
    """
    Test Vault — luu secrets trong memory.
    CHI dung cho unit testing.
    """

    def __init__(self, secrets: dict[str, str] | None = None):
        self._secrets = secrets or {}

    def get(self, key: str) -> str:
        if key not in self._secrets:
            raise ValueError(f"Secret '{key}' not found")
        return self._secrets[key]

    def get_or_default(self, key: str, default: str = "") -> str:
        return self._secrets.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set secret (chi cho testing)."""
        self._secrets[key] = value


# ── Factory ────────────────────────────────────────────────

_vault_instance: SecretVault | None = None


def get_vault() -> SecretVault:
    """
    Factory function — tra ve vault phu hop voi moi truong.

    Development: EnvVault (doc .env)
    Production:  Se doi sang HashiCorpVault (Phase 2)
    """
    global _vault_instance
    if _vault_instance is None:
        settings = get_settings()
        if settings.is_production:
            # Phase 2: HashiCorpVault
            logger.info("[VAULT] Production mode — using EnvVault (upgrade to HashiCorp later)")
            _vault_instance = EnvVault()
        else:
            logger.info("[VAULT] Development mode — using EnvVault")
            _vault_instance = EnvVault()
    return _vault_instance
