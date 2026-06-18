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
from app.core.dependencies import get_current_active_user, get_redis
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
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed")

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
        payment_intent_id = payment_intent.get("id")

        if not payment_intent_id:
            logger.warning("Stripe payment_intent missing id")
            return {"received": True}

        # --- C: webhook idempotency (minimal; degrade gracefully if table missing) ---
        from sqlalchemy import text as sql_text
        webhook_idempotent_checked = False
        try:
            existing = await db.execute(
                sql_text(
                    "SELECT 1 FROM stripe_webhook_events WHERE event_id = :event_id"
                ).bindparams(event_id=event.get("id"))
            )
            webhook_idempotent_checked = True
            if existing.first():
                return {"received": True}
        except Exception as e:
            # Table may not exist yet (migration not deployed). We still process
            # settlement with A+B validations, but skip idempotency persistence.
            logger.warning("Stripe webhook idempotency table missing/unavailable: %s", e)
            webhook_idempotent_checked = False


        # --- A + B: settle by PI id -> Payment -> order_id, validate amount+currency ---
        stmt_payment = select(Payment).where(
            Payment.provider == "stripe",
            Payment.provider_transaction_id == payment_intent_id,
        )
        res_payment = await db.execute(stmt_payment)
        payment_row: Payment | None = res_payment.scalar_one_or_none()

        if not payment_row:
            logger.error("No internal Payment row for Stripe payment_intent=%s", payment_intent_id)
            return {"received": True}

        if not payment_row.order_id:
            logger.error("Internal Payment row missing order_id for Stripe payment_intent=%s", payment_intent_id)
            return {"received": True}

        # Validate status from Stripe intent
        if payment_intent.get("status") != "succeeded":
            return {"received": True}

        # amount is stored in internal Payment.amount as a decimal (major units)
        expected_amount = int(Decimal(str(payment_row.amount)) * 100)
        stripe_amount = payment_intent.get("amount")
        if stripe_amount != expected_amount:
            logger.error(
                "Amount mismatch for Stripe payment_intent=%s. Stripe=%s Internal=%s",
                payment_intent_id,
                stripe_amount,
                expected_amount,
            )
            return {"received": True}

        stripe_currency = (payment_intent.get("currency") or "").lower()
        internal_currency = (payment_row.currency or "").lower()
        if stripe_currency != internal_currency:
            logger.error(
                "Currency mismatch for Stripe payment_intent=%s. Stripe=%s Internal=%s",
                payment_intent_id,
                stripe_currency,
                internal_currency,
            )
            return {"received": True}

        # Confirm internal payment (OrderService will check order status)
        order_service = OrderService(db, redis_client=redis)
        try:
            await order_service.confirm_payment(payment_row.order_id, payment_intent_id)
        except Exception as e:
            # If OrderService rejects due to status, treat as idempotent
            logger.info("Order confirmation skipped/failed (idempotent): %s", e)

        # Mark Payment completed if not already
        if payment_row.status != PaymentStatus.COMPLETED.value:
            payment_row.status = PaymentStatus.COMPLETED.value
            payment_row.result_code = "COMPLETED"
            payment_row.raw_payload = str(payment_intent)[:5000]
            await db.commit()

        # Record webhook processed
        await db.execute(
            sql_text(
                "INSERT INTO stripe_webhook_events(event_id, event_type, processed_at) "
                "VALUES (:event_id, :event_type, NOW())"
            ).bindparams(
                event_id=event.get("id"),
                event_type=event.get("type"),
            )
        )
        await db.commit()


    return {"received": True}

