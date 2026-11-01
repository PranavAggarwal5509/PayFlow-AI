import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, TimestampMixin
from app.models.enums import POStatus, VendorStatus


class Vendor(IdMixin, TimestampMixin, Base):
    __tablename__ = "vendors"

    vendor_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gstin: Mapped[str | None] = mapped_column(String(15), unique=True)
    address: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=VendorStatus.ACTIVE.value, index=True)
    is_demo: Mapped[bool] = mapped_column(default=False)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")


class PurchaseOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=POStatus.ACTIVE.value, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    is_demo: Mapped[bool] = mapped_column(default=False)

    vendor: Mapped[Vendor] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["POAllocation"]] = relationship(back_populates="purchase_order")
    line_allocations: Mapped[list["POLineAllocation"]] = relationship(back_populates="purchase_order")


class PurchaseOrderItem(IdMixin, Base):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    line_allocations: Mapped[list["POLineAllocation"]] = relationship(back_populates="purchase_order_item")


class POAllocation(IdMixin, TimestampMixin, Base):
    """Approved invoice consumption of a PO. Remaining balance = PO total − SUM(ACTIVE allocations).

    Pending/rejected invoices never have an allocation row, so they cannot consume balance.
    """

    __tablename__ = "po_allocations"
    __table_args__ = (
        UniqueConstraint("invoice_id", name="uq_po_allocation_invoice"),
        Index("ix_po_alloc_po_status", "purchase_order_id", "status"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"))
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    allocated_by: Mapped[str] = mapped_column(String(100), default="system")

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="allocations")


class POLineAllocation(IdMixin, TimestampMixin, Base):
    """Granular quantity consumption per PO line item by approved invoices."""

    __tablename__ = "po_line_allocations"
    __table_args__ = (
        UniqueConstraint("invoice_line_item_id", name="uq_po_line_alloc_invoice_line"),
        Index("ix_po_line_alloc_item_status", "purchase_order_item_id", "status"),
        Index("ix_po_line_alloc_invoice", "invoice_id"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    purchase_order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_order_items.id"), index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), index=True)
    invoice_line_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice_line_items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    allocated_by: Mapped[str] = mapped_column(String(100), default="system")

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="line_allocations")
    purchase_order_item: Mapped[PurchaseOrderItem] = relationship(back_populates="line_allocations")


__all__ = ["POAllocation", "POLineAllocation", "PurchaseOrder", "PurchaseOrderItem", "Uuid", "Vendor"]

