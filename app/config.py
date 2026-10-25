"""
Centralized application configuration.

Uses Pydantic Settings for environment variable management.
All services reference this single configuration object.
"""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Values can be overridden via .env file or direct environment variables.
    Prefix all env vars with the application name for production deployments.
    """

    # ──────────────────────────────────────────
    # Application
    # ──────────────────────────────────────────
    APP_NAME: str = "Kanwar Sahayata"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    LOG_LEVEL: str = "INFO"

    # ──────────────────────────────────────────
    # Database
    # ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./kanwar_demo.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_POOL_TIMEOUT: int = 30

    # ──────────────────────────────────────────
    # Redis
    # ──────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # ──────────────────────────────────────────
    # Celery
    # ──────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ──────────────────────────────────────────
    # JWT Authentication
    # ──────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720  # 12 hours for shift-based operations

    # ──────────────────────────────────────────
    # MinIO Object Storage
    # ──────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "kanwar-sahayata"
    MINIO_SECURE: bool = False

    # ──────────────────────────────────────────
    # NIC SMS Gateway
    # ──────────────────────────────────────────
    SMS_GATEWAY_URL: Optional[str] = None
    SMS_GATEWAY_API_KEY: Optional[str] = None

    # ──────────────────────────────────────────
    # Firebase Cloud Messaging
    # ──────────────────────────────────────────
    FCM_SERVER_KEY: Optional[str] = None

    # ──────────────────────────────────────────
    # NIC HSM (Hardware Security Module)
    # ──────────────────────────────────────────
    HSM_ENABLED: bool = False
    HSM_PKCS11_LIB_PATH: Optional[str] = None
    HSM_SLOT_ID: Optional[int] = None
    HSM_KEY_LABEL: str = "kanwar-qr-signing-key"

    # ──────────────────────────────────────────
    # CORS
    # ──────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ──────────────────────────────────────────
    # Rate Limiting
    # ──────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()