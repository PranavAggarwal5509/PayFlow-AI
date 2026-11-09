from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser, get_current_user
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def read_settings(
    settings: Settings = Depends(get_settings), user: CurrentUser = Depends(get_current_user)
):
    """Read-only view of the business-rule configuration (secrets are never returned)."""
    return ApiResponse(
        data={
            "user": {"id": user.id, "name": user.name, "role": user.role},
            "environment": settings.environment,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.gemini_model if settings.llm_provider == "gemini" else "mock-catalog",
            "llm_configured": bool(settings.gemini_api_key) if settings.llm_provider == "gemini" else True,
            "max_upload_size_mb": settings.max_upload_size_mb,
            "supported_currencies": sorted(settings.currency_set),
            "inr_rounding_tolerance": str(settings.inr_rounding_tolerance),
            "default_rounding_tolerance": str(settings.default_rounding_tolerance),
            "require_gstin_for_approval": settings.require_gstin_for_approval,
            "vendor_fuzzy_threshold": settings.vendor_fuzzy_threshold,
            "duplicate_number_similarity": settings.duplicate_number_similarity,
            "duplicate_window_days": settings.duplicate_window_days,
            "auto_approval_limit_inr": str(settings.auto_approval_limit_inr),
            "fx_rates_to_inr": {k: str(v) for k, v in settings.fx_table.items() if k != "INR"},
            "valid_gst_rates": [f"{r.normalize():f}" for r in sorted(settings.gst_rate_set)],
            "auto_approve_inferred_po": settings.auto_approve_inferred_po,
            "po_line_price_tolerance_pct": str(settings.po_line_price_tolerance_pct),
        }
    )
