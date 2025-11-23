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
    """Configuration for the Schema Mapping service."""

    # Service metadata
    SERVICE_NAME: str = shared_settings.SCHEMA_MAPPING_SERVICE_NAME
    SERVICE_VERSION: str = shared_settings.SCHEMA_MAPPING_SERVICE_VERSION
    APP_HOST: str = Field(
        default=shared_settings.SCHEMA_MAPPING_SERVICE_HOST,
        validation_alias=AliasChoices("HOST", "APP_HOST"),
    )
    APP_PORT: int = Field(
        default=shared_settings.SCHEMA_MAPPING_SERVICE_PORT,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
    )
    APP_ENV: str = shared_settings.APP_ENV
    DEBUG: bool = Field(
        default=shared_settings.SCHEMA_MAPPING_DEBUG,
        validation_alias=AliasChoices("DEBUG", "APP_DEBUG"),
    )

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = shared_settings.SCHEMA_MAPPING_LOG_FILE

    # CORS
    CORS_ORIGINS: str = shared_settings.SCHEMA_MAPPING_CORS_ORIGINS
    CORS_ALLOW_CREDENTIALS: bool = True

    # LLM Configuration
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
    
    # Gemini Configuration
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        validation_alias="GEMINI_MODEL",
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

    # MongoDB Configuration
    MONGODB_URI: str = Field(
        default=shared_settings.MONGODB_URI,
        validation_alias=AliasChoices("MONGODB_URI", "MONGO_URI"),
    )
    DATABASE_NAME: str = Field(
        default=shared_settings.DATABASE_NAME,
        validation_alias=AliasChoices("DATABASE_NAME", "MONGO_DB"),
    )
    COLLECTION_NAME: str = Field(
        default="schema_mapping",
        validation_alias=AliasChoices("COLLECTION_NAME", "MONGO_COLLECTION"),
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

