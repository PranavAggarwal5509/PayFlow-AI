from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import POStatus, VendorStatus
from app.schemas.common import ORMModel
from app.utils.normalize import normalize_gstin


class VendorBase(BaseModel):
    vendor_name: str = Field(min_length=2, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    status: VendorStatus = VendorStatus.ACTIVE

    @field_validator("gstin")
    @classmethod
    def _clean_gstin(cls, value: str | None) -> str | None:
        return normalize_gstin(value)


class VendorCreate(VendorBase):
    vendor_code: str | None = Field(default=None, max_length=32)


class VendorUpdate(BaseModel):
    vendor_name: str | None = Field(default=None, min_length=2, max_length=255)
    gstin: str | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    status: VendorStatus | None = None

    @field_validator("gstin")
    @classmethod
    def _clean_gstin(cls, value: str | None) -> str | None:
        return normalize_gstin(value)


class VendorOut(ORMModel):
    id: UUID
    vendor_code: str
    vendor_name: str
    gstin: str | None
    address: str | None
    email: str | None
    phone: str | None
    status: str
    is_demo: bool
    created_at: datetime
    invoice_count: int = 0
    total_invoice_value: Decimal = Decimal("0")


class POItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class POItemOut(ORMModel):
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal


class POCreate(BaseModel):
    po_number: str = Field(min_length=3, max_length=40)
    vendor_id: UUID
    po_date: date
    currency: str = Field(min_length=3, max_length=3)
    total_amount: Decimal = Field(gt=0)
    description: str | None = None
    status: POStatus = POStatus.ACTIVE
    items: list[POItemIn] = []

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class POUpdate(BaseModel):
    po_date: date | None = None
    total_amount: Decimal | None = Field(default=None, gt=0)
    description: str | None = None
    status: POStatus | None = None


class POOut(ORMModel):
    id: UUID
    po_number: str
    vendor_id: UUID
    vendor_name: str
    po_date: date
    currency: str
    total_amount: Decimal
    consumed_amount: Decimal
    remaining_balance: Decimal
    status: str
    description: str | None
    is_demo: bool


class LinkedInvoice(ORMModel):
    id: UUID
    invoice_number: str | None
    total_amount: Decimal | None
    currency: str | None
    decision_status: str | None
    allocated: bool


class PODetail(POOut):
    items: list[POItemOut]
    invoices: list[LinkedInvoice]

