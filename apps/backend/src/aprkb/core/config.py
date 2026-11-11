"""Cấu hình ứng dụng, đọc từ biến môi trường (.env)."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root_env_file() -> Path | None:
    """Locate the monorepo-root .env file; absent in a standalone container checkout."""
    parents = Path(__file__).resolve().parents
    return parents[5] / ".env" if len(parents) > 5 else None


_ROOT_ENV_FILE = _find_root_env_file()
DEV_APP_ENVS = frozenset({"local", "test"})
# Public OAuth web client ID (not a secret: every browser receives it). GOOGLE_CLIENT_ID
# overrides it; each origin serving the web app must be an authorized JavaScript origin.
DEFAULT_GOOGLE_CLIENT_ID = (
    "669298541726-qma0h92u20kkaomionj7d62ibn6u2v46.apps.googleusercontent.com"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV_FILE, extra="ignore")

    app_env: str = "local"
    app_secret_key: str = "change-me"
    google_client_id: str = DEFAULT_GOOGLE_CLIENT_ID
    api_cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("google_client_id", mode="before")
    @classmethod
    def blank_google_client_id_uses_default(cls, value: object) -> object:
        # An empty GOOGLE_CLIENT_ID= line in a deploy .env must not disable Google sign-in.
        return DEFAULT_GOOGLE_CLIENT_ID if value is None or str(value).strip() == "" else value

    database_url: str = "postgresql+asyncpg://aprkb:aprkb@localhost:5432/aprkb"
    blob_dir: str = "./data/blobs"
    log_level: str = "INFO"
    reference_library_enabled: bool = False
    # ADR-0015: separate Metric & Measurement catalog. On by default so a fresh checkout can
    # test it after `make migrate seed`; set MEASUREMENT_ENABLED=false to hide it.
    measurement_enabled: bool = True
    nlp_engine: Literal["regex", "spacy"] = "regex"
    nlp_model: str = "en_core_web_sm"
    mining_hybrid_enabled: bool = False
    # Set by the production image build (BUILD_COMMIT_SHA); never a self-asserted image digest.
    build_commit_sha: str = "unknown"

    job_lease_seconds: float = Field(default=300, gt=0)
    job_heartbeat_seconds: float = Field(default=30, gt=0)
    job_timeout_seconds: float = Field(default=900, gt=0)
    job_retry_base_seconds: float = Field(default=10, gt=0)
    job_retry_cap_seconds: float = Field(default=300, gt=0)
    job_manual_retry_limit: int = Field(default=3, ge=1, le=100)
    job_failure_alert_threshold: int = Field(default=3, ge=1, le=100)

    @model_validator(mode="after")
    def valid_job_timing(self) -> "Settings":
        if self.job_heartbeat_seconds >= self.job_lease_seconds / 2:
            raise ValueError("JOB_HEARTBEAT_SECONDS must be less than half JOB_LEASE_SECONDS")
        if self.job_retry_base_seconds > self.job_retry_cap_seconds:
            raise ValueError("JOB_RETRY_BASE_SECONDS must not exceed JOB_RETRY_CAP_SECONDS")
        if self.job_timeout_seconds <= self.job_heartbeat_seconds:
            raise ValueError("JOB_TIMEOUT_SECONDS must exceed JOB_HEARTBEAT_SECONDS")
        return self

    # Nguồn bài báo ngoài (ADR-0005): chỉ worker gọi, mặc định "null" (không nhập gì).
    article_source: str = "null"
    article_import_batch_limit: int = 20
    slr_api_base_url: str = "https://slr-api.hyperdatalab.org/api"
    slr_api_key: SecretStr | None = None
    slr_timeout_seconds: float = 30
    slr_max_retries: int = 3
    slr_max_download_bytes: int = 50 * 1024 * 1024
    # Chỉ dùng khi phát triển: gán license này cho bài SLR không có license.
    # TODO(owner, BR-10): bỏ trước khi lên production; app không khởi động nếu đặt ngoài local/test.
    slr_dev_fallback_license: str | None = None
    gold_labeler: str = "null"
    frame_labeler: str = "null"
    epistemic_labeler: Literal["null", "groq"] = "null"
    groq_api_key: SecretStr | None = None
    groq_allow_external_processing: bool = False

    @field_validator("slr_api_key", "slr_dev_fallback_license", "groq_api_key", mode="before")
    @classmethod
    def empty_value_is_missing(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("measurement_enabled", mode="before")
    @classmethod
    def blank_measurement_flag_uses_default(cls, value: object) -> object:
        # An empty MEASUREMENT_ENABLED= line (old .env copies) keeps the feature on.
        return True if value is None or str(value).strip() == "" else value

    @model_validator(mode="after")
    def dev_license_fallback_only_in_development(self) -> "Settings":
        if self.slr_dev_fallback_license is not None and self.app_env not in DEV_APP_ENVS:
            raise ValueError(
                "SLR_DEV_FALLBACK_LICENSE is only allowed when APP_ENV is local or test"
            )
        return self

    @model_validator(mode="after")
    def gold_labeler_dev_only(self) -> "Settings":
        if self.gold_labeler not in {"null", "groq"}:
            raise ValueError("GOLD_LABELER must be null or groq")
        if self.gold_labeler == "groq" and self.app_env not in DEV_APP_ENVS:
            raise ValueError("GOLD_LABELER=groq is only allowed in local or test")
        return self

    @model_validator(mode="after")
    def frame_labeler_dev_only(self) -> "Settings":
        if self.frame_labeler not in {"null", "groq"}:
            raise ValueError("FRAME_LABELER must be null or groq")
        if self.frame_labeler == "groq" and self.app_env not in DEV_APP_ENVS:
            raise ValueError("FRAME_LABELER=groq is only allowed in local or test")
        return self

    @model_validator(mode="after")
    def epistemic_labeler_dev_only(self) -> "Settings":
        if self.epistemic_labeler == "groq" and self.app_env not in DEV_APP_ENVS:
            raise ValueError("EPISTEMIC_LABELER=groq is only allowed in local or test")
        return self

    grobid_url: str = "http://localhost:8070"
    languagetool_url: str = "http://localhost:8010"

    # Privacy (NFR-05): không lưu manuscript raw mặc định.
    store_manuscript_raw: bool = False
    recommendation_log_retention_days: int = 90


settings = Settings()
