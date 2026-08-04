from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from redis import asyncio as aioredis
import json
import logging
from decimal import Decimal

from app.db.session import get_db
from app.core.dependencies import get_redis
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.services.order_service import OrderService
from app.services.paypal_service import PayPalService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["PayPal Webhooks"])

RELEVANT_EVENTS = {
    "CHECKOUT.ORDER.APPROVED",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.DENIED",
    "PAYMENT.CAPTURE.REFUNDED",
}


@router.post("/webhooks/paypal")
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    body = await request.body()

    webhook_id = settings.PAYPAL_WEBHOOK_ID
    if not webhook_id:
        logger.error("PAYPAL_WEBHOOK_ID not configured -- rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    paypal = PayPalService()
    try:
        valid = await paypal.verify_webhook_signature(
            headers={k.lower(): v for k, v in request.headers.items()},
            body=body,
            webhook_id=webhook_id,
        )
    except Exception:
        logger.error("PayPal webhook verification request failed", exc_info=True)
        raise HTTPException(status_code=400, detail="Verification failed")

    if not valid:
        logger.warning("PayPal webhook signature invalid")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(body)
    event_type = event.get("event_type")
    event_id = event.get("id")

    if event_type not in RELEVANT_EVENTS:
        return {"status": "ignored"}

    dedup_key = f"paypal:webhook:seen:{event_id}"
    already_seen = await redis.set(dedup_key, "1", nx=True, ex=86400 * 7)
    if not already_seen:
        return {"status": "duplicate_ignored"}

    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        await _handle_capture_completed(resource, db, redis)
    elif event_type == "PAYMENT.CAPTURE.DENIED":
        await _handle_capture_denied(resource, db)
    elif event_type == "PAYMENT.CAPTURE.REFUNDED":
        await _handle_refund(resource, db)
    elif event_type == "CHECKOUT.ORDER.APPROVED":
        logger.info("PayPal order approved: %s", resource.get("id"))

    return {"status": "processed"}


def _get_payment_where(resource: dict) -> tuple | None:
    """Resolve a (paypal_order_id, capture_id) pair from a capture event."""
    capture_id = resource.get("id")
    paypal_order_id = (
        resource.get("supplementary_data", {})
        .get("related_ids", {})
        .get("order_id")
    )
    if not paypal_order_id and not capture_id:
        return None
    return (paypal_order_id, capture_id)


async def _handle_capture_completed(resource: dict, db: AsyncSession, redis: aioredis.Redis):
    capture_id = resource.get("id")
    amount = resource.get("amount", {}).get("value")
    currency = resource.get("amount", {}).get("currency_code")

    ids = _get_payment_where(resource)
    if not ids:
        logger.error("Webhook capture event missing ids: %s", resource)
        return
    paypal_order_id, _ = ids

    # provider_transaction_id holds the PayPal order id before capture and the
    # capture id after; match either.
    stmt = select(Payment).where(
        Payment.provider == "paypal",
        or_(
            Payment.provider_transaction_id == paypal_order_id,
            Payment.provider_transaction_id == capture_id,
        ),
    ).with_for_update()
    res = await db.execute(stmt)
    payment = res.scalar_one_or_none()
    if not payment:
        logger.error("No Payment row found for PayPal order %s / capture %s", paypal_order_id, capture_id)
        return

    order_res = await db.execute(
        select(Order).where(Order.id == payment.order_id).with_for_update()
    )
    order = order_res.scalar_one_or_none()
    if not order:
        logger.error("Payment %s has no matching order", payment.id)
        return

    # Reconcile against the USD amount stored at create-order time.
    expected_usd = payment.amount_usd if payment.amount_usd is not None else Decimal(order.total)
    if currency != "USD" or Decimal(str(amount)) != expected_usd:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "WEBHOOK_AMOUNT_MISMATCH"
        await db.commit()
        logger.critical(
            "PayPal webhook amount mismatch order=%s expected=%s got=%s %s -- "
            "money may have moved, needs manual review/refund",
            order.id, expected_usd, amount, currency,
        )
        return

    if order.status == OrderStatus.PAID:
        return

    order_service = OrderService(db=db, redis_client=redis)
    await order_service.confirm_payment(order.id, capture_id)

    payment.status = PaymentStatus.COMPLETED.value
    payment.result_code = "COMPLETED"
    payment.provider_transaction_id = capture_id
    payer = resource.get("payer") or {}
    if payer.get("payer_id"):
        payment.payer_id = payer["payer_id"]
    await db.commit()


async def _handle_capture_denied(resource: dict, db: AsyncSession):
    ids = _get_payment_where(resource)
    if not ids:
        return
    paypal_order_id, capture_id = ids

    stmt = select(Payment).where(
        Payment.provider == "paypal",
        or_(
            Payment.provider_transaction_id == paypal_order_id,
            Payment.provider_transaction_id == capture_id,
        ),
    )
    res = await db.execute(stmt)
    payment = res.scalar_one_or_none()
    if payment and payment.status != PaymentStatus.COMPLETED.value:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "DENIED"
        await db.commit()


async def _handle_refund(resource: dict, db: AsyncSession):
    """Apply a refund state to the matching payment for reconciliation."""
    capture_id = resource.get("id")
    if not capture_id:
        logger.error("PayPal refund webhook missing capture id: %s", resource)
        return

    ids = _get_payment_where(resource)
    paypal_order_id = ids[0] if ids else None

    stmt = select(Payment).where(
        Payment.provider == "paypal",
        or_(
            Payment.provider_transaction_id == capture_id,
            Payment.provider_transaction_id == paypal_order_id,
        ),
    ).with_for_update()
    res = await db.execute(stmt)
    payment = res.scalar_one_or_none()
    if not payment:
        logger.error("No Payment row found for PayPal refund capture %s", capture_id)
        return

    refund_amount = resource.get("amount", {}).get("value")
    payment.status = PaymentStatus.REFUNDED.value
    payment.result_code = "REFUNDED"
    await db.commit()
    logger.warning(
        "PayPal refund recorded payment=%s capture=%s amount=%s",
        payment.id, capture_id, refund_amount,
    )
