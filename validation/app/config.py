"""Configuration for validation service"""

from pathlib import Path
import sys

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.shared_settings import shared_settings


class Settings(BaseSettings):
    """Configuration for the Validation service."""

    # Service metadata
    SERVICE_NAME: str = shared_settings.VALIDATION_SERVICE_NAME
    SERVICE_VERSION: str = shared_settings.VALIDATION_SERVICE_VERSION
    APP_HOST: str = Field(
        default=shared_settings.VALIDATION_SERVICE_HOST,
        validation_alias=AliasChoices("HOST", "APP_HOST"),
    )
    APP_PORT: int = Field(
        default=shared_settings.VALIDATION_SERVICE_PORT,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
    )
    APP_ENV: str = shared_settings.APP_ENV
    DEBUG: bool = Field(
        default=shared_settings.VALIDATION_DEBUG,
        validation_alias=AliasChoices("DEBUG", "APP_DEBUG"),
    )

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = shared_settings.VALIDATION_LOG_FILE

    # CORS
    CORS_ORIGINS: str = shared_settings.VALIDATION_CORS_ORIGINS
    CORS_ALLOW_CREDENTIALS: bool = True

    # LLM Configuration (for summarization)
    OPENAI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "API_KEY"),
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias="LLM_MODEL",
    )
    LLM_TEMPERATURE: float = Field(
        default=0.0,
        validation_alias="LLM_TEMPERATURE",
    )

    # PostgreSQL Configuration
    POSTGRES_HOST: str = Field(
        default=shared_settings.POSTGRES_HOST,
        validation_alias=AliasChoices("POSTGRES_HOST", "DB_HOST"),
    )
    POSTGRES_PORT: int = Field(
        default=shared_settings.POSTGRES_PORT,
        validation_alias=AliasChoices("POSTGRES_PORT", "DB_PORT"),
    )
    POSTGRES_USER: str = Field(
        default=shared_settings.POSTGRES_USER,
        validation_alias=AliasChoices("POSTGRES_USER", "DB_USER"),
    )
    POSTGRES_PASSWORD: str = Field(
        default=shared_settings.POSTGRES_PASSWORD,
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "DB_PASSWORD"),
    )
    POSTGRES_DB: str = Field(
        default=shared_settings.POSTGRES_DB,
        validation_alias=AliasChoices("POSTGRES_DB", "DB_NAME"),
    )

    model_config = SettingsConfigDict(
        env_file=[str(SERVICE_DIR / ".env"), str(ROOT_DIR / ".env")],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

