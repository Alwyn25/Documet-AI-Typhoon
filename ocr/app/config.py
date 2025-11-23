from pathlib import Path
import sys
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.shared_settings import shared_settings


class Settings(BaseSettings):
    """Configuration for the OCR service."""

    # Service metadata
    SERVICE_NAME: str = shared_settings.OCR_SERVICE_NAME
    SERVICE_VERSION: str = shared_settings.OCR_SERVICE_VERSION
    APP_HOST: str = Field(
        default=shared_settings.OCR_SERVICE_HOST,
        validation_alias=AliasChoices("HOST", "APP_HOST"),
    )
    APP_PORT: int = Field(
        default=shared_settings.OCR_SERVICE_PORT,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
    )
    APP_ENV: str = shared_settings.APP_ENV
    DEBUG: bool = Field(
        default=shared_settings.OCR_DEBUG,
        validation_alias=AliasChoices("DEBUG", "APP_DEBUG"),
    )

    # MongoDB
    MONGODB_URI: str = Field(
        default=shared_settings.OCR_MONGODB_URI,
        validation_alias=AliasChoices("MONGODB_URI", "MONGO_URL"),
    )
    DATABASE_NAME: str = Field(
        default=shared_settings.OCR_DATABASE_NAME,
        validation_alias=AliasChoices("DATABASE_NAME", "OCR_DATABASE_NAME"),
    )
    COLLECTION_NAME: str = Field(
        default=shared_settings.OCR_COLLECTION_NAME,
        validation_alias=AliasChoices("COLLECTION_NAME", "OCR_COLLECTION_NAME"),
    )

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = shared_settings.OCR_LOG_FILE

    # CORS
    CORS_ORIGINS: str = shared_settings.OCR_CORS_ORIGINS
    CORS_ALLOW_CREDENTIALS: bool = True

    # External integrations / credentials (override via environment variables)
    TYPHOON_OCR_API_KEY: Optional[str] = None
    TYPHOON_BASE_URL: str = shared_settings.TYPHOON_BASE_URL
    TYPHOON_MODEL: str = shared_settings.TYPHOON_MODEL
    TYPHOON_TASK_TYPE: str = shared_settings.TYPHOON_TASK_TYPE
    TYPHOON_MAX_TOKENS: int = shared_settings.TYPHOON_MAX_TOKENS
    TYPHOON_TEMPERATURE: float = shared_settings.TYPHOON_TEMPERATURE
    TYPHOON_TOP_P: float = shared_settings.TYPHOON_TOP_P
    TYPHOON_REPETITION_PENALTY: float = shared_settings.TYPHOON_REPETITION_PENALTY
    GPT4_VISION_API_KEY: Optional[str] = shared_settings.GPT4_VISION_API_KEY
    GPT4_VISION_MODEL: str = shared_settings.GPT4_VISION_MODEL
    GPT4_VISION_MAX_TOKENS: int = shared_settings.GPT4_VISION_MAX_TOKENS
    OPENAI_API_KEY: Optional[str] = None
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: Optional[str] = None
    AZURE_DOCUMENT_INTELLIGENCE_KEY: Optional[str] = None
    TESSERACT_CMD_PATH: Optional[str] = None
    EASYOCR_LANGUAGES: str = Field(
        default=shared_settings.OCR_EASYOCR_LANGUAGES,
        validation_alias=AliasChoices("EASYOCR_LANGUAGES", "OCR_EASYOCR_LANGUAGES"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def easyocr_languages_list(self) -> List[str]:
        return [lang.strip() for lang in self.EASYOCR_LANGUAGES.split(",") if lang.strip()]


settings = Settings()

