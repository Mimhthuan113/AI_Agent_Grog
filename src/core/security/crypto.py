"""
Crypto Module — AES-256-GCM Encryption
========================================
Mã hoá dữ liệu nhạy cảm (conversation memory, user context).

AES-256-GCM đảm bảo:
  - Confidentiality: dữ liệu bị mã hoá
  - Integrity: phát hiện tampering (GCM tag)
  - Authenticity: chỉ ai có key mới giải mã được

Sử dụng config field `db_encryption_key` đã có sẵn trong config.py (L88).
"""

from __future__ import annotations

import os
import json
import base64
import hashlib
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class CryptoError(Exception):
    """Lỗi mã hoá / giải mã."""


class AESCrypto:
    """
    AES-256-GCM encryption/decryption.

    Key derivation:
      - Nếu user cung cấp passphrase → SHA-256 hash thành 32 bytes
      - Nếu user cung cấp 32/44 bytes → dùng trực tiếp

    Format ciphertext (base64):
      [12-byte nonce][ciphertext + 16-byte tag]
    """

    NONCE_SIZE = 12  # 96 bits — recommended cho GCM

    def __init__(self, key: str | bytes | None = None):
        if key is None:
            # Tạo random key nếu không cung cấp (dev mode)
            self._key = AESGCM.generate_key(bit_length=256)
            logger.warning("[CRYPTO] Using random key — data sẽ mất khi restart!")
        elif isinstance(key, bytes) and len(key) == 32:
            self._key = key
        elif isinstance(key, str):
            if len(key) == 0:
                self._key = AESGCM.generate_key(bit_length=256)
                logger.warning("[CRYPTO] Empty key — using random key")
            else:
                # Derive 32-byte key từ passphrase bằng SHA-256
                self._key = hashlib.sha256(key.encode("utf-8")).digest()
        else:
            raise CryptoError("Key phải là 32 bytes hoặc string passphrase")

        self._gcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """
        Mã hoá plaintext → base64 string.

        Args:
            plaintext: Dữ liệu cần mã hoá (string)

        Returns:
            Base64-encoded string chứa [nonce + ciphertext + tag]
        """
        nonce = os.urandom(self.NONCE_SIZE)
        ct = self._gcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, ciphertext_b64: str) -> str:
        """
        Giải mã base64 ciphertext → plaintext string.

        Raises:
            CryptoError nếu dữ liệu bị tampering hoặc key sai.
        """
        try:
            raw = base64.b64decode(ciphertext_b64)
            nonce = raw[:self.NONCE_SIZE]
            ct = raw[self.NONCE_SIZE:]
            plaintext = self._gcm.decrypt(nonce, ct, None)
            return plaintext.decode("utf-8")
        except Exception as e:
            raise CryptoError(f"Giải mã thất bại: {e}") from e

    def encrypt_dict(self, data: dict) -> str:
        """Mã hoá dict → base64 string."""
        return self.encrypt(json.dumps(data, ensure_ascii=False))

    def decrypt_dict(self, ciphertext_b64: str) -> dict:
        """Giải mã base64 string → dict."""
        plaintext = self.decrypt(ciphertext_b64)
        return json.loads(plaintext)


# ── Singleton ──────────────────────────────────────────────

_instance: AESCrypto | None = None


def get_crypto() -> AESCrypto:
    """Trả về singleton AESCrypto, key từ config.py."""
    global _instance
    if _instance is None:
        from src.config import get_settings
        settings = get_settings()
        _instance = AESCrypto(key=settings.db_encryption_key)
    return _instance
