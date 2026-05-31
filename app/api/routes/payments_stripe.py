from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis import asyncio as aioredis
from uuid import UUID
from decimal import Decimal
import logging


try:
    import stripe  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    stripe = None


from app.db.session import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.stripe import StripeIntentRequest, StripeIntentResponse
from app.services.order_service import OrderService
from app.services.stripe_service import StripeService
from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe"])


@router.post(
    "/create-payment-intent",
    response_model=StripeIntentResponse,
)
async def create_payment_intent(
    payload: StripeIntentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Load and validate order
    stmt = select(Order).where(Order.id == payload.order_id)
    res = await db.execute(stmt)
    order: Order | None = res.scalar_one_or_none()

    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order already processed (status={order.status.value})",
        )

    amount_cents = int(Decimal(str(order.total)) * 100)

    # Create a pending Payment row so we can tie webhook -> internal payment row
    payment = Payment(
        order_id=order.id,
        provider="stripe",
        status=PaymentStatus.PENDING.value,
        amount=order.total,
        currency=settings.STRIPE_CURRENCY,
        phone=None,
        checkout_request_id=None,
        mpesa_receipt=None,
        result_code=None,
        raw_payload=None,
        provider_transaction_id=None,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    stripe_service = StripeService()
    intent = await stripe_service.create_payment_intent(
        amount_cents=amount_cents,
        currency=settings.STRIPE_CURRENCY,
        order_id=str(order.id),
        payment_id=str(payment.id),
    )

    # Persist Stripe IDs (source of truth will still be webhook)
    payment.provider_transaction_id = intent.id
    try:
        payment.raw_payload = str(getattr(intent, "latest_charge", None))[:5000]
    except Exception:
        payment.raw_payload = None

    await db.commit()

    return StripeIntentResponse(client_secret=intent.client_secret)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Important: Stripe requires the raw body bytes
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    # Handle only what we need
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]

        metadata = payment_intent.get("metadata") or {}
        order_id = metadata.get("order_id")
        payment_id = metadata.get("payment_id")

        if not order_id:
            logger.warning("Stripe payment_intent missing order_id metadata")
            return {"received": True}

        # Idempotency: avoid confirming same Stripe PaymentIntent multiple times
        existing_payment = None
        if payment_id:
            stmt = select(Payment).where(Payment.id == UUID(payment_id), Payment.provider == "stripe")
            res = await db.execute(stmt)
            existing_payment = res.scalar_one_or_none()

        # Confirm internal payment (OrderService will check order status)
        order_service = OrderService(db, redis_client= None)
        try:
            await order_service.confirm_payment(UUID(order_id), payment_intent.get("id"))
        except Exception as e:
            # If OrderService rejects due to status, treat as idempotent
            logger.info("Order confirmation skipped/failed (idempotent): %s", e)

        # Update Payment row if we can locate it
        # Prefer updating by payment_intent id because payment_id may be absent
        stmt_payment = select(Payment).where(
            Payment.provider == "stripe",
            Payment.provider_transaction_id == payment_intent.get("id"),
        )
        res_payment = await db.execute(stmt_payment)
        payment_row: Payment | None = res_payment.scalar_one_or_none()

        if payment_row and payment_row.status != PaymentStatus.COMPLETED.value:
            payment_row.status = PaymentStatus.COMPLETED.value
            payment_row.result_code = "COMPLETED"
            payment_row.provider_transaction_id = payment_intent.get("id")
            payment_row.raw_payload = str(payment_intent)[:5000]
            await db.commit()

    return {"received": True}

