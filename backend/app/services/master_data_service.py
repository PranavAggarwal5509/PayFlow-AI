"""Vendor and purchase-order maintenance."""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.vendor_po import PurchaseOrder, PurchaseOrderItem, Vendor
from app.schemas.master_data import POCreate, POUpdate, VendorCreate, VendorUpdate
from app.services.audit_service import record_audit
from app.utils.normalize import normalize_vendor_name


def create_vendor(db: Session, data: VendorCreate, *, user_id: str) -> Vendor:
    if data.gstin and db.scalar(select(Vendor).where(Vendor.gstin == data.gstin)):
        raise ConflictError("A vendor with this GSTIN already exists.")
    code = data.vendor_code or _next_vendor_code(db)
    if db.scalar(select(Vendor).where(Vendor.vendor_code == code)):
        raise ConflictError(f"Vendor code {code} already exists.")
    vendor = Vendor(
        vendor_code=code,
        vendor_name=data.vendor_name.strip(),
        normalized_name=normalize_vendor_name(data.vendor_name),
        gstin=data.gstin,
        address=data.address,
        email=data.email,
        phone=data.phone,
        status=data.status.value,
    )
    db.add(vendor)
    record_audit(db, action="VENDOR_CREATED", actor_type="USER", actor_id=user_id,
                 new_value=vendor.vendor_name, description=f"Vendor {code} created.")  # fmt: skip
    db.commit()
    return vendor


def _next_vendor_code(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Vendor)) or 0
    number = count + 1
    while db.scalar(select(Vendor).where(Vendor.vendor_code == f"V-{number:04d}")):
        number += 1
    return f"V-{number:04d}"


def update_vendor(db: Session, vendor_id: UUID, data: VendorUpdate, *, user_id: str) -> Vendor:
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise NotFoundError("Vendor not found.")
    changes = data.model_dump(exclude_unset=True)
    if "gstin" in changes and changes["gstin"]:
        clash = db.scalar(select(Vendor).where(Vendor.gstin == changes["gstin"], Vendor.id != vendor_id))
        if clash:
            raise ConflictError("Another vendor already uses this GSTIN.")
    for key, value in changes.items():
        old = getattr(vendor, key)
        new = value.value if hasattr(value, "value") else value
        if key == "vendor_name" and new:
            vendor.normalized_name = normalize_vendor_name(new)
        if old != new:
            setattr(vendor, key, new)
            record_audit(db, action="VENDOR_UPDATED", actor_type="USER", actor_id=user_id,
                         old_value=str(old), new_value=str(new),
                         description=f"{vendor.vendor_code}: {key} changed.")  # fmt: skip
    db.commit()
    return vendor


def create_purchase_order(db: Session, data: POCreate, *, user_id: str) -> PurchaseOrder:
    if db.get(Vendor, data.vendor_id) is None:
        raise NotFoundError("Vendor not found.")
    if db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == data.po_number)):
        raise ConflictError(f"Purchase order {data.po_number} already exists.")
    po = PurchaseOrder(
        po_number=data.po_number.strip(),
        vendor_id=data.vendor_id,
        po_date=data.po_date,
        currency=data.currency,
        total_amount=data.total_amount,
        status=data.status.value,
        description=data.description,
        items=[
            PurchaseOrderItem(
                description=i.description,
                quantity=i.quantity,
                unit_price=i.unit_price,
                total_amount=(i.quantity * i.unit_price).quantize(Decimal("0.01"), ROUND_HALF_UP),
            )
            for i in data.items
        ],
    )
    db.add(po)
    record_audit(db, action="PO_CREATED", actor_type="USER", actor_id=user_id,
                 new_value=po.po_number, description=f"PO {po.po_number} created.")  # fmt: skip
    db.commit()
    return po


def update_purchase_order(db: Session, po_id: UUID, data: POUpdate, *, user_id: str) -> PurchaseOrder:
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update())
    if po is None:
        raise NotFoundError("Purchase order not found.")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        new = value.value if hasattr(value, "value") else value
        old = getattr(po, key)
        if old != new:
            setattr(po, key, new)
            record_audit(db, action="PO_UPDATED", actor_type="USER", actor_id=user_id,
                         old_value=str(old), new_value=str(new),
                         description=f"{po.po_number}: {key} changed.")  # fmt: skip
    db.commit()
    return po

