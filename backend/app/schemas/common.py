from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    """Every public endpoint returns this envelope."""

    data: T | None = None
    meta: PageMeta | None = None
    error: ErrorBody | None = None


def page_meta(page: int, page_size: int, total: int) -> PageMeta:
    return PageMeta(
        page=page, page_size=page_size, total=total, total_pages=max(1, -(-total // page_size))
    )


__all__ = ["ApiResponse", "Decimal", "ORMModel", "PageMeta", "UUID", "date", "datetime", "page_meta"]

