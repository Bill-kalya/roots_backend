from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Dict, List

from app.core.dependencies import get_current_user, get_redis
from app.db.session import get_db
from app.models.receipt import Receipt
from app.services.receipt_service import generate_receipt, verify_receipt


router = APIRouter(prefix="/api/v1/receipts", tags=["receipts"])


@router.post("/generate", summary="Generate receipt after payment confirmation")
async def create_receipt(
    payload: Dict[str, Any],
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Receipt minting is restricted.

    This endpoint can be used by server-side flows only. If called by a
    regular user, block the request to prevent receipt forgery.
    """

    # Minimal protection: require an admin user.
    # If your auth system supports roles differently, update `is_admin`.
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "role", None) == "admin")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        receipt = await generate_receipt(db=db, **payload)
        return receipt
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verify/{receipt_id}", summary="Public receipt verification")
async def verify(receipt_id: str, db: AsyncSession = Depends(get_db)):
    result = await verify_receipt(receipt_id, db)
    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"])
    # summary only
    return result


@router.get("/{receipt_id}", summary="Fetch full receipt (owner only)")
async def get_receipt(receipt_id: str, current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row_res = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    row = row_res.scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")

    import json

    data = json.loads(row.payload)
    if data.get("customer_email") != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return data

