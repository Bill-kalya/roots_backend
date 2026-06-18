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
from app.core.dependencies import get_current_user



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
        select(Order).where(Order.id == order_id_raw)
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

    try:
        response = await MpesaService().stk_push(
            phone=phone,
            amount=str(canonical_amount),
            order_reference=order_reference,
        )

    except Exception as exc:
        logger.exception(
            "STK push failed phone=%s amount=%s",
            phone,
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
        status=PaymentStatus.PENDING,
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


    if payment.status in (
        PaymentStatus.COMPLETED,
        PaymentStatus.FAILED,
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
            try:
                callback_amount_int = int(float(callback_amount))
            except (TypeError, ValueError):
                logger.error(
                    "Amount mismatch (invalid callback amount) payment_id=%s expected=%s received=%s",
                    payment.id,
                    payment.amount,
                    callback_amount,
                )
                payment.status = PaymentStatus.FAILED
                payment.result_code = result_code
                await db.commit()
                return {"ResultCode": 0, "ResultDesc": "Accepted"}

            if int(float(payment.amount)) != callback_amount_int:
                logger.error(
                    "Amount mismatch payment_id=%s expected=%s received=%s",
                    payment.id,
                    payment.amount,
                    callback_amount_int,
                )
                payment.status = PaymentStatus.FAILED
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
                await order_service.confirm_payment(
                    payment.order_id,
                    payment.mpesa_receipt,
                )
            except ValueError as exc:
                logger.error(
                    "confirm_payment failed order_id=%s error=%s",
                    payment.order_id,
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


    try:
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

