"""Vendor and purchase-order queries (list, detail, aggregates)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.invoice import Invoice
from app.models.vendor_po import POAllocation, PurchaseOrder, Vendor
from app.schemas.master_data import LinkedInvoice, PODetail, POItemOut, POOut, VendorOut


def vendor_out(db: Session, vendor: Vendor) -> VendorOut:
    count, total = db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.vendor_id == vendor.id
        )
    ).one()
    out = VendorOut.model_validate(vendor)
    out.invoice_count = count
    out.total_invoice_value = Decimal(total)
    return out


def list_vendors(
    db: Session, q: str | None, status: str | None, sort_by: str, descending: bool, page: int, size: int
) -> tuple[list[VendorOut], int]:
    stmt = select(Vendor)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Vendor.vendor_name.ilike(like), Vendor.vendor_code.ilike(like), Vendor.gstin.ilike(like))
        )
    if status:
        stmt = stmt.where(Vendor.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    columns = {"vendor_name": Vendor.vendor_name, "vendor_code": Vendor.vendor_code,
               "status": Vendor.status, "created_at": Vendor.created_at}  # fmt: skip
    column = columns.get(sort_by, Vendor.vendor_name)
    stmt = stmt.order_by(column.desc() if descending else column.asc()).offset((page - 1) * size).limit(size)
    vendors = list(db.scalars(stmt))
    return [vendor_out(db, v) for v in vendors], total


def _po_out(db: Session, po: PurchaseOrder, cls=POOut):
    consumed = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(POAllocation.amount), 0)).where(
                POAllocation.purchase_order_id == po.id, POAllocation.status == "ACTIVE"
            )
        )
        or 0
    )
    return dict(
        id=po.id, po_number=po.po_number, vendor_id=po.vendor_id, vendor_name=po.vendor.vendor_name,
        po_date=po.po_date, currency=po.currency, total_amount=po.total_amount,
        consumed_amount=consumed, remaining_balance=po.total_amount - consumed, status=po.status,
        description=po.description, is_demo=po.is_demo,
    )  # fmt: skip


def po_out(db: Session, po: PurchaseOrder) -> POOut:
    return POOut(**_po_out(db, po))


def po_detail(db: Session, po_id: UUID) -> PODetail | None:
    po = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == po_id)
        .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.vendor))
    )
    if po is None:
        return None
    allocated_ids = {
        a.invoice_id
        for a in db.scalars(
            select(POAllocation).where(
                POAllocation.purchase_order_id == po.id, POAllocation.status == "ACTIVE"
            )
        )
    }
    invoices = db.scalars(
        select(Invoice).where(Invoice.purchase_order_id == po.id).order_by(Invoice.uploaded_at.desc())
    )
    return PODetail(
        **_po_out(db, po),
        items=[POItemOut.model_validate(i) for i in po.items],
        invoices=[
            LinkedInvoice(
                id=i.id, invoice_number=i.invoice_number, total_amount=i.total_amount,
                currency=i.currency, decision_status=i.decision_status,
                allocated=i.id in allocated_ids,
            )  # fmt: skip
            for i in invoices
        ],
    )


def list_purchase_orders(
    db: Session, q: str | None, status: str | None, vendor_id: UUID | None,
    sort_by: str, descending: bool, page: int, size: int,
) -> tuple[list[POOut], int]:  # fmt: skip
    stmt = select(PurchaseOrder).join(Vendor, PurchaseOrder.vendor_id == Vendor.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(PurchaseOrder.po_number.ilike(like), Vendor.vendor_name.ilike(like)))
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if vendor_id:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    columns = {"po_number": PurchaseOrder.po_number, "po_date": PurchaseOrder.po_date,
               "total_amount": PurchaseOrder.total_amount, "status": PurchaseOrder.status}  # fmt: skip
    column = columns.get(sort_by, PurchaseOrder.po_date)
    stmt = (
        stmt.options(selectinload(PurchaseOrder.vendor))
        .order_by(column.desc() if descending else column.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return [po_out(db, po) for po in db.scalars(stmt)], total
