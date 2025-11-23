from pathlib import Path
import sys
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from config.shared_settings import shared_settings


class Settings(BaseSettings):
    """Configuration for the ingestion service."""

    SERVICE_NAME: str = shared_settings.INGESTION_SERVICE_NAME
    SERVICE_VERSION: str = shared_settings.INGESTION_SERVICE_VERSION
    APP_HOST: str = Field(
        default=shared_settings.INGESTION_SERVICE_HOST,
        validation_alias=AliasChoices("HOST", "APP_HOST"),
    )
    APP_PORT: int = Field(
        default=shared_settings.INGESTION_SERVICE_PORT,
        validation_alias=AliasChoices("PORT", "APP_PORT"),
    )
    APP_ENV: str = shared_settings.APP_ENV
    DEBUG: bool = Field(
        default=shared_settings.INGESTION_DEBUG,
        validation_alias=AliasChoices("DEBUG", "APP_DEBUG"),
    )

    STORAGE_ROOT: Path = Field(
        default=Path(shared_settings.INGESTION_STORAGE_DIR),
        validation_alias=AliasChoices("STORAGE_ROOT", "UPLOAD_ROOT"),
    )
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "tiff",
            "bmp",
            "gif",
            "webp",
            "doc",
            "docx",
        ]
    )
    MAX_FILE_SIZE_MB: int = Field(default=25, validation_alias="MAX_FILE_SIZE_MB")

    CORS_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = True

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
    def storage_root_path(self) -> Path:
        storage_root = Path(self.STORAGE_ROOT)
        if storage_root.is_absolute():
            return storage_root

        parts = storage_root.parts
        if parts and parts[0].lower() == "ingestion":
            storage_root = Path(*parts[1:]) if len(parts) > 1 else Path()

        return (SERVICE_DIR / storage_root).resolve()


settings = Settings()


