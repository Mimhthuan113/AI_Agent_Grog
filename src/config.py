"""
Config Module — Pydantic Settings
===================================
Đọc toàn bộ configuration từ file .env
Sử dụng Pydantic Settings để validate type + default values.

Nguyên tắc:
- KHÔNG hardcode bất kỳ secret nào
- Mọi config đều từ environment variables
- Có default hợp lý cho dev, KHÔNG có default cho secrets
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application Settings — loaded from .env file."""

    # ── APP ─────────────────────────────────────────────────
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    # ── GROQ API (LLM) ─────────────────────────────────────
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_model_default: str = Field(
        default="llama3-8b-8192", alias="GROQ_MODEL_DEFAULT"
    )
    groq_model_smart: str = Field(
        default="llama-3.3-70b-versatile", alias="GROQ_MODEL_SMART"
    )
    groq_max_tokens: int = Field(default=512, alias="GROQ_MAX_TOKENS")
    groq_temperature: float = Field(default=0.0, alias="GROQ_TEMPERATURE")
    groq_timeout: int = Field(default=10, alias="GROQ_TIMEOUT")

    # ── JWT AUTH ────────────────────────────────────────────
    jwt_private_key_path: str = Field(
        default="./keys/private.pem", alias="JWT_PRIVATE_KEY_PATH"
    )
    jwt_public_key_path: str = Field(
        default="./keys/public.pem", alias="JWT_PUBLIC_KEY_PATH"
    )
    jwt_algorithm: str = Field(default="RS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )

    # ── ADMIN ACCOUNT ──────────────────────────────────────
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(..., alias="ADMIN_PASSWORD")

    # ── REDIS ──────────────────────────────────────────────
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    # ── DATABASE ───────────────────────────────────────────
    sqlite_db_path: str = Field(
        default="./data/audit.db", alias="SQLITE_DB_PATH"
    )

    # ── HOME ASSISTANT ─────────────────────────────────────
    ha_base_url: str = Field(
        default="http://homeassistant.local:8123", alias="HA_BASE_URL"
    )
    ha_token: str = Field(default="", alias="HA_TOKEN")
    ha_timeout: int = Field(default=5, alias="HA_TIMEOUT")
    ha_verify_ssl: bool = Field(default=False, alias="HA_VERIFY_SSL")

    # ── MQTT ───────────────────────────────────────────────
    mqtt_broker_host: str = Field(default="localhost", alias="MQTT_BROKER_HOST")
    mqtt_broker_port: int = Field(default=8883, alias="MQTT_BROKER_PORT")
    mqtt_username: str = Field(default="smarthub", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")

    # ── ENCRYPTION ─────────────────────────────────────────
    db_encryption_key: str = Field(default="", alias="DB_ENCRYPTION_KEY")

    # ── RATE LIMITING ──────────────────────────────────────
    rate_limit_per_user_per_minute: int = Field(
        default=10, alias="RATE_LIMIT_PER_USER_PER_MINUTE"
    )
    rate_limit_per_entity_per_minute: int = Field(
        default=3, alias="RATE_LIMIT_PER_ENTITY_PER_MINUTE"
    )
    rate_limit_per_user_per_hour: int = Field(
        default=50, alias="RATE_LIMIT_PER_USER_PER_HOUR"
    )
    circuit_breaker_threshold: int = Field(
        default=5, alias="CIRCUIT_BREAKER_THRESHOLD"
    )
    circuit_breaker_timeout_sec: int = Field(
        default=60, alias="CIRCUIT_BREAKER_TIMEOUT_SEC"
    )

    # ── SECURITY ───────────────────────────────────────────
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )
    allow_plain_http: bool = Field(default=True, alias="ALLOW_PLAIN_HTTP")

    # ── Computed Properties ────────────────────────────────

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string thành list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def redis_url(self) -> str:
        """Build Redis URL từ config."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def load_jwt_private_key(self) -> str:
        """Đọc RSA private key từ file PEM."""
        path = Path(self.jwt_private_key_path)
        if not path.exists():
            raise FileNotFoundError(
                f"JWT private key not found at: {path.absolute()}\n"
                "Run: python infrastructure/scripts/gen_jwt_keys.py"
            )
        return path.read_text()

    def load_jwt_public_key(self) -> str:
        """Đọc RSA public key từ file PEM."""
        path = Path(self.jwt_public_key_path)
        if not path.exists():
            raise FileNotFoundError(
                f"JWT public key not found at: {path.absolute()}\n"
                "Run: python infrastructure/scripts/gen_jwt_keys.py"
            )
        return path.read_text()

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton Settings instance.
    Cached bằng lru_cache — chỉ đọc .env 1 lần duy nhất.
    """
    return Settings()
