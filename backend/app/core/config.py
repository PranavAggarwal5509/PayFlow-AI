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
    cors_origins: str = "*"

    upload_dir: Path = Path("../storage/uploads")
    max_upload_size_mb: int = 15

    storage_backend: Literal["local", "supabase"] = "supabase"
    supabase_url: str = "https://etrvyixknoxwfwnqrbws.supabase.co"
    supabase_service_role_key: str = ""
    supabase_bucket: str = "PayFlow"

    inr_rounding_tolerance: Decimal = Decimal("1.00")
    default_rounding_tolerance: Decimal = Decimal("0.01")
    po_line_price_tolerance_pct: Decimal = Decimal("0.05")  # 5% line unit price variance tolerance
    supported_currencies: str = "INR,USD,EUR,GBP,AED,SGD"
    require_gstin_for_approval: bool = True

    vendor_fuzzy_threshold: int = 88
    duplicate_number_similarity: int = 85
    duplicate_window_days: int = 90  # potential-duplicate look-back, by invoice date

    # Delegation of authority: invoices above this INR-equivalent value always need a human approver.
    auto_approval_limit_inr: Decimal = Decimal("400000")
    # Indicative FX used only to compare foreign invoices against the INR approval limit.
    fx_rates_to_inr: str = "USD:83.50,EUR:90.20,GBP:105.60,AED:22.70,SGD:62.10"
    valid_gst_rates: str = "0,0.1,0.25,1.5,3,5,6,12,18,28,40"
    # A PO implied from vendor + line items is suggested, never silently used for auto-approval.
    auto_approve_inferred_po: bool = False
    # Optional presentation pacing between pipeline stages (0 = off). Real work still runs; this
    # only keeps each stage visible long enough to follow in a live demo.
    stage_pacing_ms: int = Field(default=0, ge=0, le=5000)
    ocr_min_chars_per_page: int = 40
    ocr_dpi: int = 200

    demo_user_email: str = "reviewer@payflow.local"
    demo_user_name: str = "Demo Reviewer"

    # Sign-in. AUTH_SECRET must be set to a long random value outside development.
    auth_secret: str = "dev-only-insecure-secret-change-me"
    auth_session_ttl_hours: int = 12
    auth_remember_ttl_hours: int = 24 * 14
    # Seeds one demo account per role and lists them on the sign-in page (turn off for real use).
    enable_demo_accounts: bool = True
    # Lets an administrator wipe live demo uploads from the UI (seeded history is never touched).
    allow_demo_reset: bool = True

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.environment == "production" and self.llm_provider == "mock":
            raise ValueError("LLM_PROVIDER=mock is forbidden in production environment")
        if self.environment == "production" and self.auth_secret.startswith("dev-only"):
            raise ValueError("AUTH_SECRET must be set to a strong random value in production")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def currency_set(self) -> set[str]:
        return {c.strip().upper() for c in self.supported_currencies.split(",") if c.strip()}

    @property
    def fx_table(self) -> dict[str, Decimal]:
        table = {"INR": Decimal("1")}
        for pair in self.fx_rates_to_inr.split(","):
            if ":" in pair:
                code, rate = pair.split(":", 1)
                table[code.strip().upper()] = Decimal(rate.strip())
        return table

    @property
    def gst_rate_set(self) -> set[Decimal]:
        return {Decimal(r.strip()) for r in self.valid_gst_rates.split(",") if r.strip()}

    def tolerance_for(self, currency: str | None) -> Decimal:
        if currency and currency.upper() == "INR":
            return self.inr_rounding_tolerance
        return self.default_rounding_tolerance


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
