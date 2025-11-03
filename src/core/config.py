"""Application configuration for Seedream Bot."""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):

    # General environment
    ENV: str = "prod"
    TZ: str = "Asia/Baku"

    # Telegram bot configuration
    TELEGRAM_BOT_TOKEN: str
    WEBHOOK_USE: bool = True
    PUBLIC_BASE_URL: str
    WEBHOOK_SECRET_TOKEN: str
    ADMIN_ID: int | None = None 

    # KIE.ai (Seedream V4) API configuration
    KIE_API_KEY: str
    KIE_BASE: str = "https://api.kie.ai/api/v1"
    KIE_MODEL_EDIT: str = "bytedance/seedream-v4-edit"
    KIE_MODEL_TEXT_TO_IMAGE: str = "bytedance/seedream-v4-text-to-image"
    
    # ✅ OpenAI Whisper API
    OPENAI_API_KEY: str
    WHISPER_MODEL: str = "whisper-1"  # whisper-1 - единственная доступная модель
    
    # YooKassa configuration
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    CURRENCY: str = "RUB"
    TOPUP_RETURN_URL: str

    # MySQL database configuration
    DB_HOST: str
    DB_PORT: int = 3310
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    BROADCAST_RPS: int = 10
    BROADCAST_CONCURRENCY: int = 5
    BROADCAST_BATCH: int = 100

    # Redis configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB_FSM: int = 1
    REDIS_DB_CACHE: int = 2
    RATE_LIMIT_PER_MIN: int = 30
    REDIS_PASSWORD: str | None = None
    REDIS_DB_BROADCAST: int = 3 
    
    # ARQ job timeout (большой для 4K)
    ARQ_JOB_TIMEOUT_S: int = 900  # 15 минут

    @computed_field
    @property
    def DB_DSN(self) -> str:
        """Assemble an async MySQL DSN from discrete components."""
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )
    
settings = Settings()