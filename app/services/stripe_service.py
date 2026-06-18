from fastapi import HTTPException

try:
    import stripe  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    stripe = None

from app.core.config import settings


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

    async def create_payment_intent(
        self,
        *,
        amount_cents: int,
        currency: str,
        order_id: str,
        payment_id: str | None = None,
    ):
        # NOTE: stripe-python is synchronous. This code is called from async routes.
        # For production, consider offloading to a threadpool if needed.
        if stripe is None:  # extra guard for safety across deployments
            raise HTTPException(status_code=503, detail="Stripe SDK not installed")

        metadata = {"order_id": order_id}
        if payment_id:
            metadata["payment_id"] = payment_id

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
        return intent


