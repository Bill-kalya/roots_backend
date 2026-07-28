import asyncio
from fastapi import HTTPException

try:
    import stripe  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    stripe = None

from app.core.config import settings

STRIPE_API_VERSION = "2024-12-18.acacia"


class StripeService:
    """Stripe integration wrapper.

    Note: Stripe keys are optional during early development.
    This service will raise a clear error only when Stripe is used.
    """

    def __init__(self) -> None:
        # Defensive guard: avoid traceback if stripe-python isn't installed.
        if stripe is None:
            # 503 = service unavailable (dependency missing)
            raise HTTPException(status_code=503, detail="Stripe SDK not installed")

        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in your .env to use Stripe endpoints."
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = STRIPE_API_VERSION

    async def create_payment_intent(
        self,
        *,
        amount_cents: int,
        currency: str,
        order_id: str,
        payment_id: str | None = None,
    ):
        if stripe is None:
            raise HTTPException(status_code=503, detail="Stripe SDK not installed")

        metadata = {"order_id": order_id}
        if payment_id:
            metadata["payment_id"] = payment_id

        intent = await asyncio.to_thread(
            stripe.PaymentIntent.create,
            amount=amount_cents,
            currency=currency,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
            idempotency_key=f"order_{order_id}",
        )
        return intent


