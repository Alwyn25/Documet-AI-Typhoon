from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Loads and validates application settings from the .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080

    # Database URIs
    MONGODB_URI: str
    POSTGRES_URI: str

    # API Keys
    OPENAI_API_KEY: str

settings = Settings()
