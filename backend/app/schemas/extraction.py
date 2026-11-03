"""Strict schema for the structured output returned by the LLM."""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid amount")
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    cleaned = re.sub(r"[^\d.\-]", "", str(value).replace(",", ""))  # "₹ 1,234.50" → "1234.50"
    if cleaned in {"", "-", "."}:
        raise ValueError(f"not a number: {value!r}")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


Money = Annotated[Decimal | None, BeforeValidator(_to_decimal)]


class ExtractedLineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    quantity: Money = None
    unit_price: Money = None
    tax_percentage: Money = None
    total_amount: Money = None


class ExtractedInvoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_gstin: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD when parseable")
    due_date: str | None = None
    purchase_order_number: str | None = None
    currency: str | None = None
    subtotal: Money = None
    tax_amount: Money = None
    total_amount: Money = None
    payment_terms: str | None = None
    bank_account_details: str | None = None
    payment_instructions: str | None = None
    other_references: list[str] = Field(default_factory=list)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    # Fields the model found but is not sure about — distinct from fields that are simply absent.
    uncertain_fields: list[str] = Field(default_factory=list)
    # Telemetry captured from LLM provider (not part of invoice data)
    _telemetry: dict | None = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("invoice_number", "vendor_name", "purchase_order_number", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

