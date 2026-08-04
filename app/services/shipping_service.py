from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.db.session import get_db


@dataclass(frozen=True)
class ShippingRateOption:
    carrier: str
    service_name: str
    shipping_cost: Decimal
    currency: str
    estimated_delivery_days: int
    customs_tax_info: Optional[str] = None


# Canonical carrier multipliers shared between rate quotes and authoritative
# server-side shipping fee derivation at order time.
CARRIER_MULTIPLIERS: Dict[str, Decimal] = {
    "dhl": Decimal("1.00"),
    "fedex": Decimal("1.05"),
    "ups": Decimal("0.97"),
}


class ShippingService:
    """Shipping rate calculation service.

    Phase 1: zone-based internal pricing (no carrier API).

    Cost formula (per spec):
      - base_rate + per_kg_rate * weight_kg
      - if fragile => * 1.15

    Returns multiple carrier options (DHL/FedEx/UPS) by applying fixed multipliers
    on top of the base internal rate.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

        # Simple carrier multipliers to make UI feel like "carrier choice".
        # Phase 2 will replace with real live quotes.
        self._carrier_multipliers: Dict[str, Decimal] = dict(CARRIER_MULTIPLIERS)

        # Simple ETA presets (days)
        self._carrier_etas_days: Dict[str, int] = {
            "dhl": 3,
            "fedex": 4,
            "ups": 5,
        }

    async def get_rates(
        self,
        *,
        country: str,
        weight_kg: float,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        fragile: bool = False,
    ) -> List[ShippingRateOption]:
        # Lazy import to avoid circular deps
        from app.models.shipping_zone import ShippingZone

        country_code = (country or "").upper()
        if len(country_code) < 2:
            raise ValueError("Invalid country")

        # Package dims calculation hook (kept for Phase 2)
        # For Phase 1 we use weight only, but dims are validated/accepted.
        weight_dec = Decimal(str(weight_kg))

        # Zone lookup
        stmt = select(ShippingZone).where(ShippingZone.country_code == country_code)
        res = await self.db.execute(stmt)
        zone: ShippingZone | None = res.scalar_one_or_none()

        if not zone:
            raise ValueError(f"No shipping zone configured for {country_code}")

        base = Decimal(str(zone.base_rate))
        per_kg = Decimal(str(zone.per_kg_rate))

        internal_rate = base + (per_kg * weight_dec)
        if fragile:
            internal_rate = internal_rate * Decimal("1.15")

        customs_info = (
            "Import duties and taxes may be charged by your country's customs authority and are not included in the product price. "
            "Different countries have different thresholds and regulations."
        )

        # Build carrier options from internal_rate
        options: List[ShippingRateOption] = []
        for carrier, multiplier in self._carrier_multipliers.items():
            cost = (internal_rate * multiplier).quantize(Decimal("0.01"))
            options.append(
                ShippingRateOption(
                    carrier=carrier,
                    service_name=carrier.upper(),
                    shipping_cost=cost,
                    currency="USD",
                    estimated_delivery_days=self._carrier_etas_days.get(carrier, 4),
                    customs_tax_info=customs_info,
                )
            )

        return options

