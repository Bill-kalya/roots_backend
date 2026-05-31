from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal

from redis import asyncio as aioredis

from app.db.session import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.services.order_service import OrderService
from app.services.paypal_service import PayPalService
from app.schemas.paypal import (
    PayPalCreateOrderRequest,
    PayPalCreateOrderResponse,
    PayPalCaptureRequest,
    PayPalCaptureResponse,
)

import logging
logger = logging.getLogger(__name__)
router = APIRouter(tags=["PayPal"])


@router.post("/create-order", response_model=PayPalCreateOrderResponse)
async def paypal_create_order(

    payload: PayPalCreateOrderRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate order ownership + status
    stmt = select(Order).where(Order.id == payload.order_id)
    res = await db.execute(stmt)
    order: Order | None = res.scalar_one_or_none()

    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is not pending (status={order.status.value})",
        )

    # Amount/currency verification (server-side)
    expected_total = Decimal(str(order.total))
    if Decimal(str(payload.amount)) != expected_total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount does not match order total",
        )

    if payload.currency != "USD":
        # PayPal integration expects USD only
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PayPal currency must be USD")

    # Create a pending Payment row so capture is idempotent/tracked
    # (We do not capture here; only create PayPal order)
    payment = Payment(
        order_id=order.id,
        provider="paypal",
        status=PaymentStatus.PENDING.value,
        amount=order.total,
        currency="USD",
        phone=None,
        checkout_request_id=None,
        mpesa_receipt=None,
        result_code=None,
        raw_payload=None,
        provider_transaction_id=None,
    )

    # Commit so we have payment.id if needed later (optional)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    paypal = PayPalService()
    paypal_res = await paypal.create_order(
        total_amount=str(order.total),
        currency="USD",
        intent="CAPTURE",
    )

    # Store PayPal order id as provider_transaction_id for traceability until capture
    payment.provider_transaction_id = paypal_res.get("paypal_order_id")
    payment.raw_payload = (paypal_res.get("raw") or {})

    # raw_payload is Text; store as best-effort string
    try:
        import json

        payment.raw_payload = json.dumps(paypal_res.get("raw") or {})[:5000]
    except Exception:
        payment.raw_payload = None

    await db.commit()

    return PayPalCreateOrderResponse(
        approval_url=paypal_res["approval_url"],
        paypal_order_id=paypal_res["paypal_order_id"],
    )


@router.post("/capture", response_model=PayPalCaptureResponse)
async def paypal_capture(
    payload: PayPalCaptureRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Order).where(Order.id == payload.order_id)
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

    # Ensure we have a corresponding Payment row
    payment_stmt = select(Payment).where(
        Payment.order_id == order.id,
        Payment.provider == "paypal",
        Payment.provider_transaction_id == payload.paypal_order_id,
    )
    payment_res = await db.execute(payment_stmt)
    payment: Payment | None = payment_res.scalar_one_or_none()

    if not payment:
        # Allow capture without pre-created payment row, but safer to require it
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PayPal payment record not found")

    paypal = PayPalService()
    capture_res = await paypal.capture_order(payload.paypal_order_id)

    if capture_res.get("capture_status") != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PayPal capture not completed")

    capture_id = capture_res.get("capture_id")

    # Confirm internal payment (marks order PAID + queues fulfillment)
    order_service = OrderService(db, redis_client=None)  # inventory commit uses redis keys in some impls
    await order_service.confirm_payment(order.id, capture_id)


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

