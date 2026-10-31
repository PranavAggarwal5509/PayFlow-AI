"""Import every model so `Base.metadata` is complete (Alembic autogenerate, create_all)."""

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.processing import (
    AuditLog,
    Decision,
    NotificationDraft,
    ProcessingRun,
    Review,
    StageEvent,
    ValidationResult,
)
from app.models.vendor_po import POAllocation, PurchaseOrder, PurchaseOrderItem, Vendor

__all__ = [
    "AuditLog",
    "Decision",
    "Invoice",
    "InvoiceLineItem",
    "NotificationDraft",
    "POAllocation",
    "ProcessingRun",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Review",
    "StageEvent",
    "ValidationResult",
    "Vendor",
]

