from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.database.session import get_db
from app.models.vendor_po import PurchaseOrder, Vendor
from app.repositories import vendor_repository as repo
from app.schemas.common import ApiResponse, page_meta
from app.schemas.master_data import (
    POCreate,
    PODetail,
    POOut,
    POUpdate,
    VendorCreate,
    VendorOut,
    VendorUpdate,
)  # fmt: skip
from app.services import master_data_service as service

vendors = APIRouter(prefix="/vendors", tags=["Vendors"])
purchase_orders = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@vendors.get("", response_model=ApiResponse[list[VendorOut]])
def list_vendors(
    q: str | None = None,
    status: str | None = Query(None, pattern="^(ACTIVE|INACTIVE|PENDING)$"),
    sort_by: str = "vendor_name",
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    items, total = repo.list_vendors(db, q, status, sort_by, sort_dir == "desc", page, page_size)
    return ApiResponse(data=items, meta=page_meta(page, page_size, total))


@vendors.get("/{vendor_id}", response_model=ApiResponse[VendorOut])
def get_vendor(vendor_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise NotFoundError("Vendor not found.")
    return ApiResponse(data=repo.vendor_out(db, vendor))


@vendors.post("", response_model=ApiResponse[VendorOut], status_code=201)
def create_vendor(
    body: VendorCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    vendor = service.create_vendor(db, body, user_id=user.id)
    return ApiResponse(data=repo.vendor_out(db, vendor))


@vendors.patch("/{vendor_id}", response_model=ApiResponse[VendorOut])
def update_vendor(
    vendor_id: UUID, body: VendorUpdate, db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):  # fmt: skip
    vendor = service.update_vendor(db, vendor_id, body, user_id=user.id)
    return ApiResponse(data=repo.vendor_out(db, vendor))


@purchase_orders.get("", response_model=ApiResponse[list[POOut]])
def list_purchase_orders(
    q: str | None = None,
    status: str | None = Query(None, pattern="^(ACTIVE|CLOSED|CANCELLED)$"),
    vendor_id: UUID | None = None,
    sort_by: str = "po_date",
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    items, total = repo.list_purchase_orders(
        db, q, status, vendor_id, sort_by, sort_dir == "desc", page, page_size
    )
    return ApiResponse(data=items, meta=page_meta(page, page_size, total))


@purchase_orders.get("/{po_id}", response_model=ApiResponse[PODetail])
def get_purchase_order(po_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    detail = repo.po_detail(db, po_id)
    if detail is None:
        raise NotFoundError("Purchase order not found.")
    return ApiResponse(data=detail)


@purchase_orders.post("", response_model=ApiResponse[POOut], status_code=201)
def create_purchase_order(
    body: POCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    po = service.create_purchase_order(db, body, user_id=user.id)
    return ApiResponse(data=repo.po_out(db, po))


@purchase_orders.patch("/{po_id}", response_model=ApiResponse[POOut])
def update_purchase_order(
    po_id: UUID, body: POUpdate, db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):  # fmt: skip
    po = service.update_purchase_order(db, po_id, body, user_id=user.id)
    return ApiResponse(data=repo.po_out(db, po))


__all__ = ["PurchaseOrder", "purchase_orders", "vendors"]
