"""LLM-based invoice extraction behind a provider abstraction.

The LLM only *reads* the document. It never decides anything about the invoice.
"""

import json
import logging
import time
from decimal import Decimal
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ProcessingError, TransientError
from app.schemas.extraction import ExtractedInvoice

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You extract structured data from invoice text. Rules:
1. Never invent values. Use null for anything not present in the text.
2. Copy amounts exactly as printed (digits only, no currency symbols). Do NOT correct or recalculate any amount.
3. Dates: output ISO YYYY-MM-DD if unambiguous, otherwise copy the original text.
4. currency: 3-letter ISO code (INR, USD, ...). Infer from symbols like ₹ / Rs only if explicit.
5. List in "uncertain_fields" the names of fields you found but are not confident about.
6. Respond with ONLY a JSON object with these keys:
vendor_name, vendor_address, vendor_gstin, invoice_number, invoice_date, due_date,
purchase_order_number, currency, subtotal, tax_amount, total_amount, payment_terms,
bank_account_details, payment_instructions, other_references (array of strings),
uncertain_fields (array of strings),
line_items (array of {description, quantity, unit_price, tax_percentage, total_amount}).

INVOICE TEXT:
"""


class LLMProvider(Protocol):
    """Implement this to add another model provider."""

    def extract_invoice(self, document_text: str) -> dict: ...


class GeminiProvider:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract_invoice(self, document_text: str) -> dict:
        if not self._settings.gemini_api_key:
            raise ProcessingError(
                "AI extraction is not configured (missing API key).", category="LLM_CONFIG"
            )
        body = {
            "contents": [{"parts": [{"text": EXTRACTION_PROMPT + document_text[:60000]}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingLevel": "low"},
                "maxOutputTokens": 4096,
            },
        }
        url = f"{self.BASE_URL}/{self._settings.gemini_model}:generateContent"
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"x-goog-api-key": self._settings.gemini_api_key},
                timeout=self._settings.gemini_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise TransientError("AI service timed out.", category="LLM_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise TransientError("AI service is unreachable.", category="LLM_NETWORK") from exc

        if response.status_code in (429, 500, 502, 503, 504):
            err_msg = ""
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", "")
            except Exception:
                pass
            if err_msg:
                logger.warning(
                    "Gemini transient service error: HTTP %s - %s", response.status_code, err_msg
                )
            else:
                logger.warning("Gemini transient service error: HTTP %s", response.status_code)
            raise TransientError("AI service is temporarily unavailable.", category="LLM_HTTP")

        if response.status_code >= 400:
            err_msg = ""
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", "")
            except Exception:
                pass
            if err_msg:
                logger.error(
                    "Gemini rejected request: HTTP %s - %s", response.status_code, err_msg
                )
            else:
                logger.error("Gemini rejected request: HTTP %s", response.status_code)
            raise ProcessingError("AI service rejected the request.", category="LLM_HTTP")
        try:
            resp_json = response.json()
            raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
            payload = json.loads(raw_text)
            # Attach telemetry metadata if present
            usage = resp_json.get("usageMetadata", {})
            if usage:
                payload["_telemetry"] = {
                    "model": self._settings.gemini_model,
                    "prompt_tokens": usage.get("promptTokenCount"),
                    "completion_tokens": usage.get("candidatesTokenCount"),
                    "total_tokens": usage.get("totalTokenCount"),
                }
            return payload
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ValueError("Gemini returned malformed JSON") from exc


class MockLLMProvider:
    """Mock extractor for offline development and testing of known synthetic invoices."""

    def __init__(self) -> None:
        self._catalog: list[dict] = []
        self._load_catalog()

    def _load_catalog(self) -> None:
        try:
            import importlib.util
            from pathlib import Path

            script_path = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "sample_catalog.py"
            if script_path.exists():
                spec_mod = importlib.util.spec_from_file_location("sample_catalog", str(script_path))
                if spec_mod and spec_mod.loader:
                    mod = importlib.util.module_from_spec(spec_mod)
                    spec_mod.loader.exec_module(mod)
                    all_specs = getattr(mod, "INVOICES", []) + getattr(mod, "HISTORY", [])
                    for s in all_specs:
                        if getattr(s, "kind", "digital") == "corrupted":
                            continue
                        sub, tax, tot = s.amounts()
                        # Clean copy_of reference if needed
                        spec_num = s.number
                        if not spec_num and getattr(s, "copy_of", None):
                            target = next((x for x in all_specs if x.file == s.copy_of), None)
                            if target:
                                s = target
                                sub, tax, tot = s.amounts()
                                spec_num = s.number

                        items = [
                            {
                                "description": desc,
                                "quantity": str(qty),
                                "unit_price": str(price),
                                "tax_percentage": str(tax_pct),
                                "total_amount": str(Decimal(str(price)) * qty),
                            }
                            for desc, qty, price, tax_pct in s.items
                        ]
                        self._catalog.append({
                            "file": s.file,
                            "number": spec_num,
                            "vendor_name": s.vendor_name,
                            "gstin": s.gstin,
                            "po": s.po,
                            "data": {
                                "vendor_name": s.vendor_name or None,
                                "vendor_address": s.vendor_address or None,
                                "vendor_gstin": s.gstin,
                                "invoice_number": spec_num,
                                "invoice_date": s.date or None,
                                "due_date": s.due or None,
                                "purchase_order_number": s.po,
                                "currency": s.currency,
                                "subtotal": str(sub),
                                "tax_amount": str(tax),
                                "total_amount": str(tot),
                                "line_items": items,
                                "other_references": ["MOCK_EXTRACTION_SOURCE=sample_catalog"],
                                "uncertain_fields": [],
                            }
                        })
        except Exception:
            logger.exception("Failed to load sample catalog into MockLLMProvider")

    def extract_invoice(self, document_text: str) -> dict:
        norm_text = document_text.replace("\r", " ").replace("\n", " ")

        # 1. First attempt exact match by invoice number
        for item in self._catalog:
            inv_num = item["number"]
            if inv_num and inv_num in norm_text:
                return dict(item["data"])

        # 2. Second attempt by PO number and Vendor name (for missing invoice number scenario)
        for item in self._catalog:
            po_num = item["po"]
            vendor_name = item["vendor_name"]
            if po_num and po_num in norm_text and vendor_name and vendor_name.lower() in norm_text.lower():
                return dict(item["data"])

        # 3. Third attempt by vendor GSTIN
        for item in self._catalog:
            gstin = item["gstin"]
            if gstin and gstin in norm_text:
                return dict(item["data"])

        # If not recognized as a known synthetic scenario, fail explicitly
        logger.warning("MockLLMProvider: Unknown invoice text could not be mapped to any known synthetic catalog entry.")
        raise ProcessingError(
            "Mock LLM could not match document text to any known synthetic invoice.",
            category="LLM_UNKNOWN_MOCK",
        )


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    return GeminiProvider(settings)


def extract_structured_invoice(
    provider: LLMProvider, document_text: str, *, max_retries: int, backoff_seconds: float = 1.0
) -> ExtractedInvoice:
    """Call the provider with retries for transient errors / invalid JSON, then validate schema."""
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            payload = provider.extract_invoice(document_text)
            if not isinstance(payload, dict):
                raise ValueError("LLM payload is not a JSON object")
            telemetry = payload.get("_telemetry")
            parsed = ExtractedInvoice.model_validate(payload)
            if telemetry:
                parsed._telemetry = telemetry
            return parsed
        except (TransientError, ValueError, ValidationError) as exc:
            # pydantic's ValidationError subclasses ValueError; both are retried.
            last_error = exc
            logger.warning(
                "LLM extraction attempt %s/%s failed: %s",
                attempt,
                max_retries,
                type(exc).__name__,
                extra={"error_category": getattr(exc, "category", "LLM_INVALID_OUTPUT")},
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)

    if isinstance(last_error, TransientError):
        raise last_error  # transient retry exhausted; run state unchanged
    raise ProcessingError(
        "The AI returned data that could not be validated after several attempts.",
        category="LLM_INVALID_OUTPUT",
    ) from last_error

