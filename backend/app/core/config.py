from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

PLACEHOLDER_SECRETS = {"", "changeme", "secret", "YOUR_RANDOM_SECRET_KEY"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "MediCart"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(default="sqlite:///./medicart_dev.db")
    db_echo: bool = False

    jwt_secret: str = Field(default="dev-only-secret-change-me-before-deploying-0000")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    frontend_url: str = "http://localhost:5173"
    extra_cors_origins: str = ""

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str | None = None
    groq_vision_model: str | None = None
    groq_timeout_seconds: float = 20.0

    ocr_engine: Literal["auto", "rapidocr", "tesseract", "none"] = "auto"
    tesseract_cmd: str | None = None
    enable_handwriting_ocr: bool = False
    handwriting_model: str = "microsoft/trocr-base-handwritten"

    # Demo default: pharmacist review is optional (the customer can ask for it). Set to true to
    # require approval before prescription-only medicines can be added to the cart or dispatched.
    require_pharmacist_approval: bool = False

    max_upload_mb: int = 10
    max_pdf_pages: int = 3

    delivery_free_above: Decimal = Decimal("499.00")
    delivery_charge: Decimal = Decimal("40.00")

    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60
    analyse_rate_limit: int = 6
    analyse_rate_window_seconds: int = 60

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @model_validator(mode="after")
    def _check_production_settings(self) -> "Settings":
        if self.app_env == "production":
            problems = []
            if self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < 32:
                problems.append("JWT_SECRET must be a random value of at least 32 characters")
            if self.jwt_secret.startswith("dev-only-secret"):
                problems.append("JWT_SECRET is still the development default")
            if not self.database_url.startswith("postgresql"):
                problems.append("DATABASE_URL must point to PostgreSQL in production")
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key and self.groq_model)

    @property
    def groq_vision_configured(self) -> bool:
        return bool(self.groq_api_key and self.groq_vision_model)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        origins = {self.frontend_url.rstrip("/")}
        if self.app_env != "production":
            origins.update(
                {
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:5174",
                    "http://127.0.0.1:5174",
                }
            )
        for item in self.extra_cors_origins.split(","):
            if item.strip():
                origins.add(item.strip().rstrip("/"))
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
