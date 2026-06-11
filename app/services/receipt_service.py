import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.cache.redis_manager import redis_manager
from app.models.receipt import Receipt


# ── Canonical field order (must never change) ───────────────────────────────
_CANONICAL_FIELDS = [
    "receipt_id",
    "order_id",
    "payment_reference",
    "payment_method",
    "total",
    "currency",
    "customer_email",
    "created_at",
]


def _canonical_string(data: Dict[str, Any]) -> str:
    return "|".join(str(data[f]) for f in _CANONICAL_FIELDS)


def _sign(canonical: str) -> str:
    return hmac.new(
        settings.RECEIPT_SECRET.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()


_TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year


async def _redis_store(receipt_id: str, payload: Dict[str, Any]) -> None:
    key = f"receipt:{receipt_id}"
    await redis_manager._client.set(key, json.dumps(payload), ex=_TTL_SECONDS)


async def _redis_fetch(receipt_id: str) -> Optional[Dict[str, Any]]:
    key = f"receipt:{receipt_id}"
    raw = await redis_manager._client.get(key)
    return json.loads(raw) if raw else None


async def generate_receipt(
    *,
    order_id: str,
    payment_reference: str,
    payment_method: str,  # "card" | "paypal" | "mpesa"
    total: float,
    currency: str,
    customer_name: str,
    customer_email: str,
    items: List[Dict[str, Any]],
    subtotal: float,
    shipping_fee: float,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Create a new signed receipt.

    Idempotency:
    - One receipt per payment_reference enforced by Redis + DB UNIQUE.
    """

    # DB unique constraint for payment_reference prevents duplicates even if Redis clears.
    existing = await db.execute(
        select(Receipt).where(Receipt.payment_reference == payment_reference)
    )
    row = existing.scalar_one_or_none()
    if row:
        cached = await _redis_fetch(row.id)
        if cached:
            return cached
        payload = json.loads(row.payload)
        await _redis_store(row.id, payload)
        return payload

    receipt_id = f"REC-{uuid.uuid4().hex[:12].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    canonical_data = {
        "receipt_id": receipt_id,
        "order_id": str(order_id),
        "payment_reference": payment_reference,
        "payment_method": payment_method,
        # string for exact comparison
        "total": str(total),
        "currency": currency,
        "customer_email": customer_email,
        "created_at": now_iso,
    }

    canonical = _canonical_string(canonical_data)
    signature = _sign(canonical)
    canonical_hash = hashlib.sha256(canonical.encode()).hexdigest()

    payload: Dict[str, Any] = {
        **canonical_data,
        "customer_name": customer_name,
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "items": items,
        "status": "paid",
        # frontend verification URL
        "verification_url": f"{settings.FRONTEND_URL.rstrip('/')}/verify/{receipt_id}",
    }

    db_row = Receipt(
        id=receipt_id,
        order_id=order_id,
        payment_reference=payment_reference,
        payment_method=payment_method,
        signature=signature,
        canonical_hash=canonical_hash,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        currency=currency,
        customer_name=customer_name,
        customer_email=customer_email,
        payload=json.dumps(payload),
        status="paid",
        created_at=datetime.fromisoformat(now_iso),
    )

    db.add(db_row)
    await db.commit()
    await db.refresh(db_row)

    await _redis_store(receipt_id, payload)
    return payload


async def verify_receipt(receipt_id: str, db: AsyncSession) -> Dict[str, Any]:
    cached = await _redis_fetch(receipt_id)

    if not cached:
        row_res = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
        row = row_res.scalar_one_or_none()
        if not row:
            return {"valid": False, "reason": "Receipt not found."}

        cached = json.loads(row.payload)
        await _redis_store(receipt_id, cached)

    canonical = _canonical_string(cached)
    expected = _sign(canonical)
    actual = cached.get("signature", "")

    if not hmac.compare_digest(expected, actual):
        return {
            "valid": False,
            "reason": "Signature mismatch. This receipt may have been tampered with.",
        }

    return {
        "valid": True,
        "receipt_id": cached["receipt_id"],
        "order_id": cached["order_id"],
        "payment_method": cached["payment_method"],
        "total": cached["total"],
        "currency": cached["currency"],
        "status": cached["status"],
        "created_at": cached["created_at"],
    }

