"""CareRoute Backend Configuration"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CareRoute API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://careroute:careroute@localhost:5432/careroute"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT (Admin)
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-strong-random-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours

    # API Key (Partner)
    API_KEY_HEADER: str = "X-API-Key"
    HMAC_TIMESTAMP_TOLERANCE: int = 300  # 5 minutes

    # UnionPay (Mock / Integration)
    UNIONPAY_BASE_URL: str = "https://unionpay-api.example.com"
    UNIONPAY_MERCHANT_ID: str = "careRoute_merchant"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # File Storage
    OSS_BUCKET: str = "careroute-reports"
    OSS_ENDPOINT: str = "https://oss.example.com"

    # Data Retention
    CUSTOMER_DATA_RETENTION_YEARS: int = 5
    TRANSACTION_LOG_RETENTION_YEARS: int = 7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
