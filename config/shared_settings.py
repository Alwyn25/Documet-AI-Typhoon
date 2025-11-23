"""Shared configuration definitions for all microservices."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]


class SharedSettings(BaseSettings):
    """Global defaults and environment-driven overrides for all services."""

    # Environment
    APP_ENV: str = "development"

    # OCR service defaults
    OCR_SERVICE_NAME: str = "DocumentAI OCR Agent"
    OCR_SERVICE_VERSION: str = "1.0.0"
    OCR_SERVICE_HOST: str = "0.0.0.0"
    OCR_SERVICE_PORT: int = 8200
    OCR_DEBUG: bool = True

    # Ingestion service defaults
    INGESTION_SERVICE_NAME: str = "DocumentAI Ingestion Agent"
    INGESTION_SERVICE_VERSION: str = "1.0.0"
    INGESTION_SERVICE_HOST: str = "0.0.0.0"
    INGESTION_SERVICE_PORT: int = 8201
    INGESTION_DEBUG: bool = True
    INGESTION_STORAGE_DIR: str = str(Path("ingestion") / "uploads")

    # Schema Mapping service defaults
    SCHEMA_MAPPING_SERVICE_NAME: str = "DocumentAI Schema Mapping Agent"
    SCHEMA_MAPPING_SERVICE_VERSION: str = "1.0.0"
    SCHEMA_MAPPING_SERVICE_HOST: str = "0.0.0.0"
    SCHEMA_MAPPING_SERVICE_PORT: int = 8202
    SCHEMA_MAPPING_DEBUG: bool = True
    SCHEMA_MAPPING_LOG_FILE: str = str(Path("logs") / "schema_mapping_agent.log")
    SCHEMA_MAPPING_CORS_ORIGINS: str = "*"

    # Validation service defaults
    VALIDATION_SERVICE_NAME: str = "DocumentAI Validation Agent"
    VALIDATION_SERVICE_VERSION: str = "1.0.0"
    VALIDATION_SERVICE_HOST: str = "0.0.0.0"
    VALIDATION_SERVICE_PORT: int = 8203
    VALIDATION_DEBUG: bool = True
    VALIDATION_LOG_FILE: str = str(Path("logs") / "validation_agent.log")
    VALIDATION_CORS_ORIGINS: str = "*"

    # MongoDB defaults
    OCR_MONGODB_URI: str = "mongodb://localhost:27017/"
    OCR_DATABASE_NAME: str = "DocumentAi"
    OCR_COLLECTION_NAME: str = "ocr_agent"
    
    # MongoDB defaults for Schema Mapping
    MONGODB_URI: str = "mongodb://localhost:27017/"
    DATABASE_NAME: str = "DocumentAi"

    # PostgreSQL defaults for Schema Mapping
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "Password123"
    POSTGRES_DB: str = "invoice_db"

    # Logging defaults
    OCR_LOG_FILE: str = str(Path("logs") / "ocr_agent.log")

    # CORS defaults
    OCR_CORS_ORIGINS: str = "*"

    # OCR engine defaults
    OCR_EASYOCR_LANGUAGES: str = "en"

    # Optional shared credentials (override via environment variables)
    TYPHOON_OCR_API_KEY: Optional[str] = None
    TYPHOON_BASE_URL: str = "https://api.opentyphoon.ai/v1"
    TYPHOON_MODEL: str = "typhoon-ocr"
    TYPHOON_TASK_TYPE: str = "default"
    TYPHOON_MAX_TOKENS: int = 16000
    TYPHOON_TEMPERATURE: float = 0.1
    TYPHOON_TOP_P: float = 0.6
    TYPHOON_REPETITION_PENALTY: float = 1.1
    GPT4_VISION_API_KEY: Optional[str] = None
    GPT4_VISION_MODEL: str = "gpt-4o"
    GPT4_VISION_MAX_TOKENS: int = 4000
    OPENAI_API_KEY: Optional[str] = None
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: Optional[str] = None
    AZURE_DOCUMENT_INTELLIGENCE_KEY: Optional[str] = None
    TESSERACT_CMD_PATH: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


shared_settings = SharedSettings()

