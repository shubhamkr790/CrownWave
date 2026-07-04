from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    """Standard response envelope for all API endpoints.

    Keeps the contract predictable for frontend consumers. Every response
    has the same shape regardless of the endpoint.
    """

    success: bool = True
    data: T | None = None
    error: str | None = None
    error_code: str | None = None
    pagination: PaginationMeta | None = None
    meta: dict[str, Any] | None = None

    @classmethod
    def ok(cls, data: T, pagination: PaginationMeta | None = None, **meta: Any) -> ApiResponse[T]:
        return cls(
            success=True,
            data=data,
            pagination=pagination,
            meta=meta if meta else None,
        )

    @classmethod
    def fail(cls, error: str, error_code: str = "UNKNOWN") -> ApiResponse[None]:
        return cls(success=False, error=error, error_code=error_code)
