from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Dict, Optional
import json
import logging
import re

from app.db.session import get_db
from app.models.payment import Payment
from app.services.mpesa_service import MpesaService

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
async def stk_push(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    try:
        phone = _normalize_phone(payload.get("phone"))
        amount = _normalize_amount(payload.get("amount"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    order_reference = (
        str(payload.get("order_reference")).strip()
        if payload.get("order_reference")
        else f"ROOTS-{phone[-4:]}"
    )

    try:
        response = await MpesaService().stk_push(
            phone=phone,
            amount=str(amount),
            order_reference=order_reference,
        )
    except Exception as exc:
        logger.exception("STK push failed phone=%s amount=%s", phone, amount)
        raise HTTPException(status_code=502, detail="M-Pesa STK push failed. Please try again.")

    checkout_request_id = response.get("CheckoutRequestID")
    merchant_request_id = response.get("MerchantRequestID")
    customer_message = response.get("CustomerMessage")

    if not checkout_request_id:
        raise HTTPException(status_code=502, detail="No CheckoutRequestID returned.")

    payment = Payment(
        provider="mpesa",
        status="pending",
        amount=str(amount),
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

    stmt = select(Payment).where(Payment.checkout_request_id == checkout_request_id)
    result = await db.execute(stmt)
    payment: Optional[Payment] = result.scalar_one_or_none()

    if not payment:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    if payment.status in ("completed", "failed"):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment.result_code = result_code

    if result_code == "0":
        payment.status = "completed"
        receipt = next((i.get("Value") for i in items if i.get("Name") == "MpesaReceiptNumber"), None)
        payment.mpesa_receipt = str(receipt) if receipt else None
        logger.info("Payment completed checkout_request_id=%s receipt=%s", checkout_request_id, payment.mpesa_receipt)
    else:
        payment.status = "failed"
        logger.warning("Payment failed checkout_request_id=%s code=%s desc=%s", checkout_request_id, result_code, result_desc)

    try:
        payment.raw_payload = json.dumps(payload)[:5000]
    except Exception:
        pass

    await db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.get("/status/{checkout_request_id}")
async def payment_status(checkout_request_id: str, db: AsyncSession = Depends(get_db)):
    if not checkout_request_id or len(checkout_request_id) > 255:
        raise HTTPException(status_code=422, detail="Invalid checkout_request_id")

    stmt = select(Payment).where(Payment.checkout_request_id == checkout_request_id)
    result = await db.execute(stmt)
    payment: Optional[Payment] = result.scalar_one_or_none()

    if not payment:
        return {"status": "not_found"}

    return {"status": payment.status, "receipt": payment.mpesa_receipt}
