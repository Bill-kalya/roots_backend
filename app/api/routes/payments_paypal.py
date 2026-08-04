from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal, ROUND_HALF_UP

from redis import asyncio as aioredis

from app.db.session import get_db
from app.core.dependencies import get_current_active_user, get_redis
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus, PaymentProvider
from app.services.order_service import OrderService
from app.services.paypal_service import PayPalService
from app.core.config import settings
from app.schemas.paypal import (
    PayPalCreateOrderRequest,
    PayPalCreateOrderResponse,
    PayPalCaptureRequest,
    PayPalCaptureResponse,
    PayPalCancelRequest,
    PayPalCancelResponse,
)


import json
import logging
logger = logging.getLogger(__name__)
router = APIRouter(tags=["PayPal"])


@router.get("/config")
async def paypal_config():
    """Public config so the checkout can show the KES -> USD conversion."""
    return {
        "currency": "USD",
        "exchange_rate": str(settings.PAYPAL_EXCHANGE_RATE),
    }


@router.post("/create-order", response_model=PayPalCreateOrderResponse)
async def paypal_create_order(
    payload: PayPalCreateOrderRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    idempotency_key = request.headers.get("Idempotency-Key")

    # Validate order ownership + status (row-locked to serialize retries)
    stmt = select(Order).where(Order.id == payload.order_id).with_for_update()
    res = await db.execute(stmt)
    order: Order | None = res.scalar_one_or_none()

    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is not pending (status={order.status.value})",
        )

    # Amount verification: the frontend sends the KES total.
    expected_total = Decimal(str(order.total))
    if Decimal(str(payload.amount)) != expected_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount does not match order total",
        )

    # PayPal processes in USD; convert the KES total server-side so the
    # customer is never charged the KES number as USD.
    rate = Decimal(str(settings.PAYPAL_EXCHANGE_RATE))
    if rate <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PayPal exchange rate not configured",
        )
    usd_amount = (expected_total / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Idempotency: reuse a single pending PayPal payment per order.
    existing_stmt = select(Payment).where(
        Payment.order_id == order.id,
        Payment.provider == PaymentProvider.PAYPAL,
        Payment.status == PaymentStatus.PENDING.value,
    ).with_for_update()
    payment: Payment | None = (await db.execute(existing_stmt)).scalar_one_or_none()

    paypal = PayPalService()
    try:
        paypal_res = await paypal.create_order(
            total_amount=str(usd_amount),
            currency="USD",
            intent="CAPTURE",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("PayPal create_order failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal request failed",
        )

    if payment is None:
        payment = Payment(
            order_id=order.id,
            provider=PaymentProvider.PAYPAL,
            status=PaymentStatus.PENDING.value,
        )
        db.add(payment)

    payment.provider_transaction_id = paypal_res["paypal_order_id"]
    payment.checkout_request_id = idempotency_key or payment.checkout_request_id
    payment.amount = usd_amount
    payment.currency = "USD"
    payment.amount_kes = expected_total
    payment.amount_usd = usd_amount
    payment.exchange_rate = rate
    payment.raw_payload = json.dumps(paypal_res.get("raw") or {})[:5000]

    await db.commit()

    return PayPalCreateOrderResponse(
        approval_url=paypal_res["approval_url"],
        paypal_order_id=paypal_res["paypal_order_id"],
        amount_usd=usd_amount,
        exchange_rate=rate,
    )


@router.post("/capture", response_model=PayPalCaptureResponse)
async def paypal_capture(
    payload: PayPalCaptureRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):

    stmt = select(Order).where(Order.id == payload.order_id).with_for_update()
    res = await db.execute(stmt)
    order: Order | None = res.scalar_one_or_none()

    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status != OrderStatus.PENDING:
        # idempotent behavior: if already paid, return success
        if order.status == OrderStatus.PAID:
            return PayPalCaptureResponse(
                success=True,
                order_status=order.status.value,
                paypal_order_id=payload.paypal_order_id,
                capture_id=order.payment_reference,
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order cannot be captured")

    # Ensure we have a corresponding Payment row (row-locked)
    payment_stmt = select(Payment).where(
        Payment.order_id == order.id,
        Payment.provider == PaymentProvider.PAYPAL,
        Payment.provider_transaction_id == payload.paypal_order_id,
    ).with_for_update()
    payment: Payment | None = (await db.execute(payment_stmt)).scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PayPal payment record not found")

    paypal = PayPalService()
    try:
        capture_res = await paypal.capture_order(payload.paypal_order_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("PayPal capture_order failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal capture failed",
        )

    if capture_res.get("capture_status") != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PayPal capture not completed")

    capture_id = capture_res.get("capture_id")

    # Reconcile captured amount/currency against the USD amount stored at
    # create-order time (fall back to order.total for legacy rows).
    captured_amount = capture_res.get("amount")
    captured_currency = capture_res.get("currency")
    expected_usd = payment.amount_usd if payment.amount_usd is not None else Decimal(str(order.total))

    if captured_currency != "USD":
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "CAPTURE_CURRENCY_MISMATCH"
        await db.commit()
        raise HTTPException(status_code=400, detail="Captured currency mismatch")

    try:
        captured_amount_dec = Decimal(str(captured_amount))
    except Exception:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "CAPTURE_AMOUNT_INVALID"
        await db.commit()
        raise HTTPException(status_code=400, detail="Captured amount invalid")

    if captured_amount_dec != expected_usd:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "CAPTURE_AMOUNT_MISMATCH"
        await db.commit()
        raise HTTPException(status_code=400, detail="Captured amount mismatch")

    # Store payer identity for reconciliation/refunds
    payer_id = payload.payer_id or capture_res.get("payer_id")
    if payer_id:
        payment.payer_id = payer_id

    # Confirm internal payment (marks order PAID + queues fulfillment)
    order_service = OrderService(db=db, redis_client=redis)
    try:
        await order_service.confirm_payment(order.id, capture_id)
    except Exception as exc:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "CAPTURE_CONFIRM_FAILED"
        await db.commit()
        logger.error("PayPal confirm_payment failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment captured by PayPal but internal confirmation failed",
        )

    # Update Payment row
    payment.status = PaymentStatus.COMPLETED.value
    payment.result_code = "COMPLETED"
    payment.raw_payload = str(capture_res.get("raw"))[:5000]
    payment.provider_transaction_id = str(capture_id or payload.paypal_order_id)

    await db.commit()

    return PayPalCaptureResponse(
        success=True,
        order_status="paid",
        paypal_order_id=payload.paypal_order_id,
        capture_id=capture_id,
    )


@router.post("/cancel", response_model=PayPalCancelResponse)
async def paypal_cancel(
    payload: PayPalCancelRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark the pending PayPal payment as cancelled when the user abandons
    checkout (called from the PayPal cancel redirect or the checkout page).
    The order stays PENDING so the existing timeout reaper handles inventory
    release (matching the M-Pesa flow)."""
    if payload.paypal_order_id:
        payment_stmt = select(Payment).where(
            Payment.provider == PaymentProvider.PAYPAL,
            Payment.provider_transaction_id == payload.paypal_order_id,
            Payment.status == PaymentStatus.PENDING.value,
        ).with_for_update()
        payment: Payment | None = (await db.execute(payment_stmt)).scalar_one_or_none()
        order_id = payment.order_id if payment else payload.order_id
    else:
        payment = None
        order_id = payload.order_id

    if not order_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="order_id or paypal_order_id required")

    stmt = select(Order).where(Order.id == order_id).with_for_update()
    res = await db.execute(stmt)
    order: Order | None = res.scalar_one_or_none()

    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if payment is None:
        payment_stmt = select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == PaymentProvider.PAYPAL,
            Payment.status == PaymentStatus.PENDING.value,
        ).with_for_update()
        payment = (await db.execute(payment_stmt)).scalar_one_or_none()

    if payment:
        payment.status = PaymentStatus.FAILED.value
        payment.result_code = "CANCELLED_BY_USER"
    await db.commit()

    return PayPalCancelResponse(success=True, order_status=order.status.value)
