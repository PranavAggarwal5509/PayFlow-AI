"""Application settings, loaded from environment variables / .env and validated at startup."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Required — startup fails with a clear message when missing.
    database_url: str = Field(..., description="SQLAlchemy URL, e.g. postgresql+psycopg://...")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: float = 45.0
    gemini_max_retries: int = 3

    llm_provider: Literal["mock", "gemini"] = "gemini"

    backend_base_url: str = "http://backend:8000"
    frontend_base_url: str = "http://localhost:3000"

    upload_dir: Path = Path("../storage/uploads")
    max_upload_size_mb: int = 15

    inr_rounding_tolerance: Decimal = Decimal("1.00")
    default_rounding_tolerance: Decimal = Decimal("0.01")
    po_line_price_tolerance_pct: Decimal = Decimal("0.05")  # 5% line unit price variance tolerance
    supported_currencies: str = "INR,USD,EUR,GBP,AED,SGD"
    require_gstin_for_approval: bool = True

    vendor_fuzzy_threshold: int = 88
    duplicate_number_similarity: int = 85
    ocr_min_chars_per_page: int = 40
    ocr_dpi: int = 200

    demo_user_email: str = "reviewer@payflow.local"
    demo_user_name: str = "Demo Reviewer"

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.environment == "production" and self.llm_provider == "mock":
            raise ValueError("LLM_PROVIDER=mock is forbidden in production environment")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def currency_set(self) -> set[str]:
        return {c.strip().upper() for c in self.supported_currencies.split(",") if c.strip()}

    def tolerance_for(self, currency: str | None) -> Decimal:
        if currency and currency.upper() == "INR":
            return self.inr_rounding_tolerance
        return self.default_rounding_tolerance


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
