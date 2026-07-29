from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Any, Dict, Optional
import json
import logging
import re

from app.db.session import get_db
from app.models.payment import Payment, PaymentStatus
from app.services.mpesa_service import MpesaService
from app.core.dependencies import (
    get_current_user,
    get_current_active_user,
)
from app.core.config import settings



logger = logging.getLogger(__name__)
router = APIRouter(tags=["M-Pesa"])

_PHONE_RE = re.compile(r"^254[71]\d{8}$")


def _normalize_phone(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("phone is required")
    n = raw.strip().replace("+", "").replace(" ", "").replace("-", "")
    if n.startswith("0"):
        n = "254" + n[1:]
    if not _PHONE_RE.match(n):
        raise ValueError("Enter a valid Safaricom number e.g. 0712 345 678")
    return n


def _normalize_amount(raw):
    try:
        v = int(float(raw))
    except (TypeError, ValueError):
        raise ValueError("amount must be a number")
    if v < 1:
        raise ValueError("amount must be at least 1 KES")
    return v


@router.post("/stk-push")
async def stk_push(
    payload: Dict[str, Any],
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        phone = _normalize_phone(payload.get("phone"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


    order_id_raw = payload.get("order_id")
    if not order_id_raw:
        raise HTTPException(status_code=422, detail="order_id is required")

    from app.models.order import Order
    order_id_raw = str(order_id_raw).strip()
    if not order_id_raw:
        raise HTTPException(status_code=422, detail="order_id is required")

    order = await db.execute(
        select(Order).where(
            Order.id == order_id_raw,
            Order.user_id == current_user.id,
        )
    )
    order_obj = order.scalar_one_or_none()
    if not order_obj:
        raise HTTPException(status_code=404, detail="Order not found")

    # Canonical amount comes from the order stored in DB (never trust client payload)
    try:
        canonical_amount = int(float(order_obj.total))
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid order total")

    if canonical_amount < 1:
        raise HTTPException(status_code=422, detail="Order total must be at least 1 KES")

    order_reference = f"ORDER-{order_obj.id}"

    # Idempotency guard: if there's already a PENDING Payment for this order,
    # return its checkout_request_id instead of firing a second STK push.
    existing_stmt = (
        select(Payment)
        .where(
            Payment.order_id == order_obj.id,
            Payment.status == PaymentStatus.PENDING.value,
        )
        .order_by(Payment.created_at.desc())
    )
    existing_result = await db.execute(existing_stmt)
    existing_payment = existing_result.scalar_one_or_none()

    if existing_payment and existing_payment.checkout_request_id:
        logger.info(
            "Reusing existing PENDING payment checkout_request_id=%s payment_id=%s",
            existing_payment.checkout_request_id,
            existing_payment.id,
        )
        return {
            "success": True,
            "checkout_request_id": existing_payment.checkout_request_id,
            "customer_message": "Check your phone and enter your M-Pesa PIN.",
        }

    try:
        response = await MpesaService().stk_push(
            phone=phone,
            amount=str(canonical_amount),
            order_reference=order_reference,
        )

    except Exception as exc:
        masked_phone = phone[:6] + "****" if len(phone) > 6 else phone
        logger.exception(
            "STK push failed phone=%s amount=%s",
            masked_phone,
            canonical_amount,
        )
        raise HTTPException(status_code=502, detail="M-Pesa STK push failed. Please try again.")


    checkout_request_id = response.get("CheckoutRequestID")
    merchant_request_id = response.get("MerchantRequestID")
    customer_message = response.get("CustomerMessage")

    if not checkout_request_id:
        raise HTTPException(status_code=502, detail="No CheckoutRequestID returned.")

    payment = Payment(
        order_id=order_obj.id,
        provider="mpesa",
        status=PaymentStatus.PENDING.value,
        amount=str(canonical_amount),
        currency="KES",
        phone=phone,
        checkout_request_id=checkout_request_id,
        provider_transaction_id=merchant_request_id or None,
        raw_payload=None,
    )


    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    logger.info("STK push OK checkout_request_id=%s payment_id=%s", checkout_request_id, payment.id)

    return {
        "success": True,
        "checkout_request_id": checkout_request_id,
        "customer_message": customer_message,
    }


@router.post("/callback")
async def mpesa_callback(request: Request, db: AsyncSession = Depends(get_db)):
    expected_secret = settings.MPESA_CALLBACK_SECRET
    if expected_secret:
        received_secret = request.headers.get("X-Mpesa-Callback-Secret")
        if not received_secret or received_secret != expected_secret:
            logger.warning(
                "Rejected M-Pesa callback with invalid or missing secret header"
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

    try:
        payload = await request.json()
    except Exception:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}


    try:
        callback = payload["Body"]["stkCallback"]
        checkout_request_id = str(callback["CheckoutRequestID"])
        result_code = str(callback.get("ResultCode", "-1"))
        result_desc = callback.get("ResultDesc", "")
        items = callback.get("CallbackMetadata", {}).get("Item", [])
    except (KeyError, TypeError):
        logger.warning("Malformed callback: %s", payload)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    stmt = (
        select(Payment)
        .where(Payment.checkout_request_id == checkout_request_id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    payment: Optional[Payment] = result.scalar_one_or_none()

    if not payment:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}


    # Payment.status is stored as a string (see Payment model), so always compare
    # against enum .value.
    if payment.status in (
        PaymentStatus.COMPLETED.value,
        PaymentStatus.FAILED.value,
    ):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}


    payment.result_code = result_code

    if result_code == "0":
        payment.status = PaymentStatus.COMPLETED

        callback_amount = next(
            (
                i.get("Value")
                for i in items
                if i.get("Name") == "Amount"
            ),
            None,
        )
        receipt = next(
            (
                i.get("Value")
                for i in items
                if i.get("Name") == "MpesaReceiptNumber"
            ),
            None,
        )

        if callback_amount is not None:
            from decimal import Decimal

            try:
                callback_amount_dec = Decimal(str(callback_amount))
                payment_amount_dec = Decimal(str(payment.amount))
            except Exception:
                logger.error(
                    "Amount mismatch (invalid callback amount) payment_id=%s expected=%s received=%s",
                    payment.id,
                    payment.amount,
                    callback_amount,
                )
                payment.status = PaymentStatus.FAILED.value
                payment.result_code = result_code
                await db.commit()
                return {"ResultCode": 0, "ResultDesc": "Accepted"}

            if payment_amount_dec != callback_amount_dec:
                logger.error(
                    "Amount mismatch payment_id=%s expected=%s received=%s",
                    payment.id,
                    payment.amount,
                    callback_amount_dec,
                )
                payment.status = PaymentStatus.FAILED.value
                payment.result_code = result_code
                await db.commit()
                return {"ResultCode": 0, "ResultDesc": "Accepted"}

        payment.mpesa_receipt = str(receipt) if receipt else None

        logger.info(
            "Payment completed checkout_request_id=%s receipt=%s",
            checkout_request_id,
            payment.mpesa_receipt,
        )


        if payment.order_id:
            from app.services.order_service import OrderService

            redis = request.app.state.redis
            order_service = OrderService(db=db, redis_client=redis)

            try:
                confirmed_order = await order_service.confirm_payment(
                    payment.order_id,
                    payment.mpesa_receipt,
                )
            except ValueError as exc:
                logger.error(
                    "confirm_payment failed order_id=%s error=%s",
                    payment.order_id,
                    exc,
                )
                # If the order was cancelled before the callback arrived,
                # the payment succeeded but the order is no longer actionable.
                # Flag for manual review rather than silently losing the payment.
                if "cannot be paid" in str(exc).lower() or "current status" in str(exc).lower():
                    logger.warning(
                        "PAYMENT_ORDER_MISMATCH order_id=%s payment_id=%s "
                        "— payment succeeded but order was already cancelled. "
                        "Requires manual reconciliation.",
                        payment.order_id,
                        payment.id,
                    )
                confirmed_order = None

            # Receipt generation (idempotent by payment_reference)
            if confirmed_order:
                try:
                    from app.services.receipt_service import generate_receipt

                    # Load customer info for receipt. Order model in this repo does
                    # not snapshot customer fields, so fall back to User.
                    customer_email = None
                    customer_name = None
                    try:
                        from app.models.user import User

                        user_stmt = select(User).where(User.id == confirmed_order.user_id)
                        user_res = await db.execute(user_stmt)
                        user = user_res.scalar_one_or_none()
                        if user:
                            customer_email = user.email
                            customer_name = getattr(user, "full_name", None) or getattr(
                                user,
                                "name",
                                None,
                            ) or str(user.id)
                    except Exception:
                        pass

                    if not customer_email:
                        # Cannot generate a valid signed receipt without customer email.
                        raise ValueError("Missing customer email")
                    if not customer_name:
                        customer_name = str(customer_email)

                    # Fetch order items for receipt line items.
                    from app.models.order import OrderItem

                    items_res = await db.execute(
                        select(OrderItem).where(
                            OrderItem.order_id == confirmed_order.id
                        )
                    )
                    items = []
                    for oi in items_res.scalars().all():
                        items.append(
                            {
                                "name": oi.name_snapshot,
                                "quantity": oi.quantity,
                                "price": str(oi.price_snapshot),
                                "line_total": str(
                                    (oi.price_snapshot * oi.quantity)
                                ),
                            }
                        )

                    # The receipt service is idempotent by payment_reference.
                    await generate_receipt(
                        db=db,
                        order_id=str(confirmed_order.id),
                        payment_reference=str(payment.mpesa_receipt)
                        if payment.mpesa_receipt
                        else str(payment.checkout_request_id),
                        payment_method="mpesa",
                        total=float(confirmed_order.total),
                        currency=str(payment.currency or "KES"),
                        customer_name=customer_name,
                        customer_email=customer_email,
                        items=items,
                        subtotal=float(confirmed_order.subtotal),
                        shipping_fee=float(confirmed_order.shipping_fee),
                    )
                except Exception as exc:
                    # Receipt generation must never break the payment callback.
                    # It is idempotent, so retry on next callback/order flow.
                    logger.error(
                        "Receipt generation failed after MPESA payment order_id=%s payment_id=%s error=%s",
                        payment.order_id,
                        payment.id,
                        exc,
                    )

    else:
        payment.status = PaymentStatus.FAILED

        logger.warning(
            "Payment failed checkout_request_id=%s code=%s desc=%s",
            checkout_request_id,
            result_code,
            result_desc,
        )


    # Avoid persisting full raw callback payload in production (contains
    # sensitive customer data like phone numbers and receipts).
    try:
        if settings.ENVIRONMENT != "production":
            payment.raw_payload = json.dumps(payload)[:5000]
    except Exception:
        pass


    await db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.get("/status/{checkout_request_id}")
async def payment_status(
    checkout_request_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    if not checkout_request_id or len(checkout_request_id) > 255:
        raise HTTPException(status_code=422, detail="Invalid checkout_request_id")

    from app.models.order import Order

    stmt = (
        select(Payment)
        .join(Order, Payment.order_id == Order.id)
        .where(
            Payment.checkout_request_id == checkout_request_id,
            Order.user_id == current_user.id,
        )
    )

    result = await db.execute(stmt)

    payment: Optional[Payment] = result.scalar_one_or_none()


    if not payment:
        return {"status": "not_found"}

    status = (
        payment.status.value
        if hasattr(payment.status, "value")
        else str(payment.status)
    )



    return {"status": status, "receipt": payment.mpesa_receipt}

