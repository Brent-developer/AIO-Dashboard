from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./biometric.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    refresh_token_days: int = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
    biometric_master_key: str = os.getenv(
        "BIOMETRIC_MASTER_KEY", "development-only-biometric-master-key"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cors_origins: tuple[str, ...] = tuple(
        value.strip()
        for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if value.strip()
    )


settings = Settings()
