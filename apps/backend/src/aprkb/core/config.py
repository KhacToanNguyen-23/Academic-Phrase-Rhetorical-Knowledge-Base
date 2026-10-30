"""Cấu hình ứng dụng, đọc từ biến môi trường (.env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_secret_key: str = "change-me"
    api_cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql+psycopg://aprkb:aprkb@localhost:5432/aprkb"
    redis_url: str = "redis://localhost:6379/0"

    # OpenAlex là adapter tùy chọn (BR-06): tắt mặc định, core vẫn chạy.
    openalex_enabled: bool = False
    openalex_api_key: str | None = None
    openalex_mailto: str | None = None

    grobid_url: str = "http://localhost:8070"
    languagetool_url: str = "http://localhost:8010"

    # Privacy (NFR-05): không lưu manuscript raw mặc định.
    store_manuscript_raw: bool = False
    recommendation_log_retention_days: int = 90


settings = Settings()
