import pytest
from decimal import Decimal

from app.core.config import Settings
from app.core.errors import ProcessingError
from app.services.llm_extractor import (
    GeminiProvider,
    MockLLMProvider,
    extract_structured_invoice,
    get_llm_provider,
)
from app.schemas.extraction import ExtractedInvoice


def test_provider_selection_mock():
    settings = Settings(
        database_url="sqlite:///./test.db",
        llm_provider="mock",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, MockLLMProvider)


def test_provider_selection_gemini():
    settings = Settings(
        database_url="sqlite:///./test.db",
        llm_provider="gemini",
        gemini_api_key="fake-key",
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, GeminiProvider)


def test_gemini_missing_api_key_raises_error():
    settings = Settings(
        database_url="sqlite:///./test.db",
        llm_provider="gemini",
        gemini_api_key="",
    )
    provider = get_llm_provider(settings)
    with pytest.raises(ProcessingError) as exc_info:
        provider.extract_invoice("Sample invoice text")
    assert "missing API key" in str(exc_info.value.message)


def test_mock_provider_extracts_known_synthetic_invoice():
    provider = MockLLMProvider()
    # ACM/2026/1042 is 01_valid_invoice
    sample_text = """
    TAX INVOICE
    Acme Industrial Supplies Pvt Ltd
    Invoice No: ACM/2026/1042
    Date: 2026-10-12
    PO Number: PO-2026-0001
    """
    extracted_dict = provider.extract_invoice(sample_text)
    assert extracted_dict["invoice_number"] == "ACM/2026/1042"
    assert extracted_dict["purchase_order_number"] == "PO-2026-0001"
    assert extracted_dict["vendor_name"] == "Acme Industrial Supplies Pvt Ltd"
    assert extracted_dict["currency"] == "INR"
    assert "line_items" in extracted_dict
    assert len(extracted_dict["line_items"]) == 2

    # Verify Pydantic validation and Decimal preservation
    extracted_model = ExtractedInvoice.model_validate(extracted_dict)
    assert isinstance(extracted_model.total_amount, Decimal)
    assert extracted_model.total_amount == Decimal("114460.00")
    assert extracted_model.subtotal == Decimal("97000.00")


def test_mock_provider_extracts_different_synthetic_invoices():
    provider = MockLLMProvider()
    
    # 02_valid_multi_line: BOS-9012
    text_bos = "Bharat Office Solutions Pvt Ltd Invoice BOS-9012 PO-2026-0002"
    data_bos = provider.extract_invoice(text_bos)
    
    # 05_exceeds_po_balance: CL-2026-248
    text_cl = "Cobalt Logistics LLP Invoice No: CL-2026-248 PO-2026-0003"
    data_cl = provider.extract_invoice(text_cl)

    assert data_bos["invoice_number"] == "BOS-9012"
    assert data_cl["invoice_number"] == "CL-2026-248"
    assert data_bos["vendor_name"] != data_cl["vendor_name"]
    assert data_bos["total_amount"] != data_cl["total_amount"]


def test_mock_provider_missing_invoice_number_scenario():
    provider = MockLLMProvider()
    # Scenario 06 has no invoice number printed, but matches PO-2026-0004 & Deccan Print
    text_06 = "Deccan Print & Packaging Ltd PO Number: PO-2026-0004 Total: 35,400"
    data_06 = provider.extract_invoice(text_06)
    assert data_06["invoice_number"] is None
    assert data_06["purchase_order_number"] == "PO-2026-0004"
    assert data_06["vendor_name"] == "Deccan Print & Packaging Ltd"


def test_mock_provider_unknown_invoice_raises_processing_error():
    provider = MockLLMProvider()
    unknown_text = "Some totally unknown invoice from an unregistered entity with random numbers 99999"
    with pytest.raises(ProcessingError) as exc_info:
        provider.extract_invoice(unknown_text)
    assert exc_info.value.category == "LLM_UNKNOWN_MOCK"


def test_extract_structured_invoice_with_mock():
    provider = MockLLMProvider()
    text = "Bharat Office Solutions Pvt Ltd BOS-9012 PO-2026-0002"
    model = extract_structured_invoice(provider, text, max_retries=1)
    assert isinstance(model, ExtractedInvoice)
    assert model.invoice_number == "BOS-9012"
    assert model.currency == "INR"

