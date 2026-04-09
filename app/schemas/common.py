from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator, create_model
from pydantic import computed_field
from typing import Optional, Generic, TypeVar, Any, Dict, List
from datetime import datetime, timezone
from enum import Enum

T = TypeVar('T')


# ---------------------------------------------------------------------------
# Core response envelope
# ---------------------------------------------------------------------------

class ResponseModel(BaseModel, Generic[T]):
    """Standard API response envelope used across all endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation successful",
                "data": {},
                "error_code": None,
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
    )

    success: bool = Field(..., description="Indicates if the operation was successful")
    message: str = Field(..., description="Human-readable response message")
    data: Optional[T] = Field(None, description="Response data payload")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the response"
    )


class ErrorResponse(BaseModel):
    """Standard error response returned on 4xx/5xx."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Validation error",
                "errors": [{"field": "email", "message": "Invalid email format"}],
                "error_code": "VALIDATION_ERROR",
                "trace_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )

    detail: str = Field(..., description="Error description")
    errors: Optional[List[Dict[str, str]]] = Field(None, description="Field-level validation errors")
    error_code: Optional[str] = Field(None, description="Application-level error code")
    trace_id: Optional[str] = Field(None, description="Request trace ID for log correlation")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

VALID_SORT_VALUES = {"price_asc", "price_desc", "newest", "popular"}


class PaginationParams:
    """
    FastAPI dependency for pagination/filtering query parameters.

    Usage:
        @router.get("/products")
        async def list_products(params: PaginationParams = Depends()):
            ...
    """

    def __init__(
        self,
        page: int = 1,
        limit: int = 12,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        origin: Optional[str] = None,
        sort: Optional[str] = None,
    ):
        if page < 1:
            raise ValueError("page must be >= 1")
        if not (1 <= limit <= 100):
            raise ValueError("limit must be between 1 and 100")
        if search is not None and not (1 <= len(search) <= 100):
            raise ValueError("search must be between 1 and 100 characters")
        if sort is not None and sort not in VALID_SORT_VALUES:
            raise ValueError(f"sort must be one of: {', '.join(sorted(VALID_SORT_VALUES))}")

        self.page = page
        self.limit = limit
        self.search = search
        self.tag = tag
        self.origin = origin
        self.sort = sort

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response with computed navigation helpers."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "limit": 12,
                "pages": 9,
                "has_next": True,
                "has_previous": False
            }
        }
    )

    items: List[T] = Field(..., description="Items for the current page")
    total: int = Field(..., ge=0, description="Total number of matching items")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, le=100, description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether a next page exists")
    has_previous: bool = Field(..., description="Whether a previous page exists")

    @classmethod
    def build(cls, items: List[T], total: int, page: int, limit: int) -> "PaginatedResponse[T]":
        """Convenience constructor — avoids computing pages/flags at call sites."""
        pages = max(1, (total + limit - 1) // limit)
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            has_next=page < pages,
            has_previous=page > 1,
        )


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class DateRangeFilter(BaseModel):
    """Reusable date-range filter applied to query endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-12-31T23:59:59Z"
            }
        }
    )

    start_date: Optional[datetime] = Field(None, description="Range start (inclusive)")
    end_date: Optional[datetime] = Field(None, description="Range end (inclusive)")

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeFilter":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


# ---------------------------------------------------------------------------
# HATEOAS / metadata
# ---------------------------------------------------------------------------

class Links(BaseModel):
    """HATEOAS navigation links attached to paginated responses."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "self": "/api/products?page=2",
                "next": "/api/products?page=3",
                "prev": "/api/products?page=1",
                "first": "/api/products?page=1",
                "last": "/api/products?page=10"
            }
        }
    )

    self_: Optional[str] = Field(None, alias="self", description="Current resource URL")
    next: Optional[str] = Field(None, description="Next page URL")
    prev: Optional[str] = Field(None, description="Previous page URL")
    first: Optional[str] = Field(None, description="First page URL")
    last: Optional[str] = Field(None, description="Last page URL")

    model_config = ConfigDict(populate_by_name=True)


class Meta(BaseModel):
    """Response metadata for observability and versioning."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-01T00:00:00Z",
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "api_version": "2.0.0",
                "processing_time_ms": 45.2
            }
        }
    )

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    api_version: str = Field(default="2.0.0", description="API version that served the request")
    processing_time_ms: Optional[float] = Field(None, description="Server-side processing time in ms")


# ---------------------------------------------------------------------------
# Dynamic model factory
# ---------------------------------------------------------------------------

def create_response_model(
    data_model: type,
    include_meta: bool = True,
    include_links: bool = False,
):
    """
    Generate a typed response wrapper for any data model at runtime.

    Example:
        ProductListResponse = create_response_model(ProductResponse, include_links=True)
    """
    fields: Dict[str, Any] = {
        "success": (bool, Field(True)),
        "message": (str, Field("Operation successful")),
        "data": (Optional[data_model], Field(None)),
    }

    if include_meta:
        fields["meta"] = (Optional[Meta], Field(None))

    if include_links:
        fields["links"] = (Optional[Links], Field(None))

    return create_model(f"{data_model.__name__}Response", **fields)


# ---------------------------------------------------------------------------
# OpenAPI customisation
# ---------------------------------------------------------------------------

class CustomOpenAPI:
    """Applies enterprise OpenAPI metadata: security schemes, tags, contact, license."""

    @staticmethod
    def apply(app: Any) -> Dict[str, Any]:
        """
        Call once during app startup, e.g. in main.py:

            app.openapi = lambda: CustomOpenAPI.apply(app)
        """
        if getattr(app, "openapi_schema", None):
            return app.openapi_schema

        schema = app.openapi()

        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT access token (Authorization: Bearer <token>)",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service communication",
            },
        }

        schema["security"] = [{"BearerAuth": []}]

        schema["info"].update({
            "contact": {
                "name": "Roots Support",
                "email": "support@roots.com",
                "url": "https://roots.com/support",
            },
            "license": {
                "name": "Proprietary",
                "url": "https://roots.com/license",
            },
        })

        schema["tags"] = [
            {"name": "Authentication", "description": "User authentication and session management"},
            {"name": "Products",       "description": "Product catalogue and search"},
            {"name": "Cart",           "description": "Shopping cart management"},
            {"name": "Orders",         "description": "Order processing and history"},
            {"name": "Testimonials",   "description": "Customer reviews and ratings"},
            {"name": "Newsletter",     "description": "Email subscription management"},
            {"name": "Health",         "description": "System health and readiness probes"},
        ]

        app.openapi_schema = schema
        return schema