"""Cấu hình ứng dụng, đọc từ biến môi trường (.env)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV_FILE = Path(__file__).resolve().parents[5] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV_FILE, extra="ignore")

    app_env: str = "local"
    app_secret_key: str = "change-me"
    api_cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql+asyncpg://aprkb:aprkb@localhost:5432/aprkb"
    blob_dir: str = "./data/blobs"
    log_level: str = "INFO"

    # Nguồn bài báo ngoài (ADR-0005): chỉ worker gọi, mặc định "null" (không nhập gì).
    article_source: str = "null"
    article_import_batch_limit: int = 20

    grobid_url: str = "http://localhost:8070"
    languagetool_url: str = "http://localhost:8010"

    # Privacy (NFR-05): không lưu manuscript raw mặc định.
    store_manuscript_raw: bool = False
    recommendation_log_retention_days: int = 90


settings = Settings()
