from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional


from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.dependencies import get_current_active_user
from app.services.shipping_service import ShippingService


router = APIRouter(tags=["Shipping"])


class ShippingRateRequest(BaseModel):
    country: str = Field(..., min_length=2, max_length=100)

    # Package characteristics (from cart/art)
    # Kept optional so Kenyan checkouts can compute shipping without requiring dimensions.
    weight_kg: Optional[float] = Field(default=None, gt=0)
    length_cm: Optional[float] = Field(default=None, gt=0)
    width_cm: Optional[float] = Field(default=None, gt=0)
    height_cm: Optional[float] = Field(default=None, gt=0)

    fragile: bool = False



class ShippingRateOptionResponse(BaseModel):
    carrier: str
    service_name: str
    shipping_cost: float
    currency: str
    estimated_delivery_days: int
    customs_tax_info: Optional[str] = None


class ShippingRatesResponse(BaseModel):
    options: List[ShippingRateOptionResponse]


@router.post("/rates", response_model=ShippingRatesResponse)
async def get_shipping_rates(
    payload: ShippingRateRequest,
    db: AsyncSession = Depends(get_db),
):
    country_code = (payload.country or "").strip().lower()

    # Kenya: shipping is free, and we intentionally do not require package dimensions.
    if country_code in {"kenya", "ke"}:
        return ShippingRatesResponse(
            options=[
                ShippingRateOptionResponse(
                    carrier="Local Delivery",
                    service_name="Local Delivery",
                    shipping_cost=0.0,
                    currency="KES",
                    estimated_delivery_days=3,
                    customs_tax_info=None,
                )
            ]
        )

    # International / non-Kenya: require the package characteristics.
    missing = [
        name
        for name, val in {
            "weight_kg": payload.weight_kg,
            "length_cm": payload.length_cm,
            "width_cm": payload.width_cm,
            "height_cm": payload.height_cm,
        }.items()
        if val is None
    ]

    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Package dimensions and weight are required for international shipping: {', '.join(missing)}",
        )

    try:
        service = ShippingService(db)
        options = await service.get_rates(
            country=payload.country,
            weight_kg=payload.weight_kg,  # type: ignore[arg-type]
            length_cm=payload.length_cm,  # type: ignore[arg-type]
            width_cm=payload.width_cm,  # type: ignore[arg-type]
            height_cm=payload.height_cm,  # type: ignore[arg-type]
            fragile=payload.fragile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ShippingRatesResponse(
        options=[
            ShippingRateOptionResponse(
                carrier=o.carrier,
                service_name=o.service_name,
                shipping_cost=float(o.shipping_cost),
                currency=o.currency,
                estimated_delivery_days=o.estimated_delivery_days,
                customs_tax_info=o.customs_tax_info,
            )
            for o in options
        ]
    )


