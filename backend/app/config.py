from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chatchat API"
    database_url: str = "sqlite:///./storage/app.db"
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model_allowlist: str = ""
    default_provider: str = "ollama"
    default_model: str = "qwen2.5:7b"
    request_timeout_seconds: float = 180.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
