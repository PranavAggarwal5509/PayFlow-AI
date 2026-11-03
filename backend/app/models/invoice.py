import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, TimestampMixin, utcnow
from app.models.enums import ProcessingStatus
from app.models.vendor_po import PurchaseOrder, Vendor


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_vendor_number", "vendor_id", "invoice_number"),
        Index("ix_invoices_status_uploaded", "decision_status", "uploaded_at"),
    )

    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    invoice_date: Mapped[date | None] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str | None] = mapped_column(String(3), index=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), index=True)

    # Values as claimed on the document (before vendor / PO resolution).
    vendor_name_raw: Mapped[str | None] = mapped_column(String(255))
    vendor_gstin_raw: Mapped[str | None] = mapped_column(String(32))
    po_number_raw: Mapped[str | None] = mapped_column(String(60))
    extracted_data: Mapped[dict | None] = mapped_column(JSON)  # full validated LLM payload
    visual_evidence: Mapped[dict | None] = mapped_column(JSON)  # visual bounding-box evidence for fields

    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(16))  # TEXT | OCR
    page_count: Mapped[int | None] = mapped_column()
    extraction_text_hash: Mapped[str | None] = mapped_column(String(64))

    processing_status: Mapped[str] = mapped_column(
        String(16), default=ProcessingStatus.PROCESSING.value, index=True
    )
    decision_status: Mapped[str | None] = mapped_column(String(16), index=True)
    uploaded_by: Mapped[str] = mapped_column(String(100), default="system")
    source_origin: Mapped[str] = mapped_column(String(32), default="LIVE_UPLOAD", index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    vendor: Mapped[Vendor | None] = relationship()
    purchase_order: Mapped[PurchaseOrder | None] = relationship()
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLineItem.position"
    )
    line_reconciliations: Mapped[list["LineItemReconciliation"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    runs: Mapped[list["ProcessingRun"]] = relationship(  # noqa: F821
        back_populates="invoice", order_by="ProcessingRun.run_number"
    )


class InvoiceLineItem(IdMixin, Base):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(default=0)
    description: Mapped[str | None] = mapped_column(String(500))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tax_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")
    reconciliation: Mapped["LineItemReconciliation | None"] = relationship(
        back_populates="invoice_line_item", uselist=False, cascade="all, delete-orphan"
    )


class LineItemReconciliation(IdMixin, TimestampMixin, Base):
    """Structured line-item matching and reconciliation against a Purchase Order line item."""

    __tablename__ = "line_item_reconciliations"
    __table_args__ = (
        UniqueConstraint("invoice_line_item_id", name="uq_line_item_recon_invoice_line"),
        Index("ix_line_recon_invoice", "invoice_id"),
        Index("ix_line_recon_po_item", "purchase_order_item_id"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    invoice_line_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoice_line_items.id", ondelete="CASCADE"), index=True
    )
    purchase_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_order_items.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    matching_method: Mapped[str] = mapped_column(String(32), nullable=False)  # EXACT | FUZZY | MANUAL | NONE
    matched_description: Mapped[str | None] = mapped_column(String(500))
    invoice_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    ordered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    allocated_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    remaining_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit_of_measure: Mapped[str | None] = mapped_column(String(32))
    invoice_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    po_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    expected_line_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    actual_line_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    explanation: Mapped[str | None] = mapped_column(Text)

    invoice: Mapped[Invoice] = relationship(back_populates="line_reconciliations")
    invoice_line_item: Mapped[InvoiceLineItem] = relationship(back_populates="reconciliation")
    purchase_order_item: Mapped["PurchaseOrderItem | None"] = relationship()

