from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from app.core.dependencies import require_merchant
from app.db.session import get_db
from app.models.user import User
from app.models.merchant_wallet import MerchantWallet
from app.models.transaction_ledger import TransactionLedger
from app.models.payout import Payout, PayoutStatus
from app.models.merchant_payout_settings import MerchantPayoutSettings
from app.services.wallet_service import WalletService
from app.schemas.merchant_payout_settings import MerchantEarningsResponse

import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Merchant - Wallet"])


@router.get("/wallet")
async def get_wallet(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    ws = WalletService(db)
    wallet = await ws.get_wallet(current_user.id)

    stmt = select(TransactionLedger).where(
        TransactionLedger.merchant_id == current_user.id
    ).order_by(TransactionLedger.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    ledger = result.scalars().all()

    return {
        "available_balance": float(wallet.available_balance),
        "pending_balance": float(wallet.pending_balance),
        "total_earned": float(wallet.total_earned),
        "total_withdrawn": float(wallet.total_withdrawn),
        "currency": wallet.currency,
        "recent_transactions": [
            {
                "id": str(t.id),
                "amount": float(t.amount),
                "entry_type": t.entry_type,
                "reference_id": t.reference_id,
                "reference_type": t.reference_type,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in ledger
        ],
    }


@router.get("/payouts")
async def get_payouts(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Payout).where(
        Payout.merchant_id == current_user.id
    ).order_by(Payout.requested_at.desc()).limit(50)
    result = await db.execute(stmt)
    payouts = result.scalars().all()

    return {
        "payouts": [
            {
                "id": str(p.id),
                "amount": float(p.amount),
                "status": p.status,
                "payout_method": p.payout_method,
                "recipient_detail": p.recipient_detail,
                "mpesa_receipt": p.mpesa_receipt,
                "error_message": p.error_message,
                "requested_at": p.requested_at.isoformat() if p.requested_at else None,
                "processed_at": p.processed_at.isoformat() if p.processed_at else None,
            }
            for p in payouts
        ],
    }


@router.post("/payouts/request")
async def request_payout(
    request: Request,
    body: dict,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    amount_raw = body.get("amount")
    if not amount_raw:
        raise HTTPException(status_code=422, detail="amount is required")

    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid amount")

    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=422, detail="Amount must be positive")

    ws = WalletService(db)
    wallet = await ws.get_wallet(current_user.id)

    if amount > wallet.available_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {wallet.available_balance}, requested: {amount}",
        )

    stmt = select(MerchantPayoutSettings).where(
        MerchantPayoutSettings.merchant_id == current_user.id
    )
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=400, detail="Configure payout settings first")

    if not settings.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Payout settings not verified. Complete the OTP verification process first.",
        )

    recipient = None
    if settings.payout_method == "MPESA":
        if settings.mpesa_mode == "PHONE":
            recipient = settings.mpesa_phone
        elif settings.mpesa_mode == "TILL":
            recipient = settings.mpesa_till_number
        elif settings.mpesa_mode == "POCHI":
            recipient = settings.pochi_phone
    elif settings.payout_method == "PAYPAL":
        recipient = settings.paypal_email
    elif settings.payout_method == "STRIPE":
        recipient = settings.stripe_account_id

    payout = Payout(
        merchant_id=current_user.id,
        amount=amount,
        currency=wallet.currency,
        status=PayoutStatus.PENDING.value,
        payout_method=settings.payout_method,
        recipient_detail=recipient,
    )
    db.add(payout)
    await db.commit()
    await db.refresh(payout)

    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    await ws.deduct_withdrawal(current_user.id, amount, payout.id, actor_id=current_user.id, ip_address=client_ip)

    logger.info("Payout %s requested for merchant %s: %.2f %s", payout.id, current_user.id, amount, wallet.currency)

    return {
        "success": True,
        "payout_id": str(payout.id),
        "amount": float(amount),
        "status": payout.status,
    }


@router.get("/ledger")
async def get_merchant_ledger(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """Get merchant transaction ledger"""
    stmt = (
        select(TransactionLedger)
        .where(TransactionLedger.merchant_id == current_user.id)
        .order_by(TransactionLedger.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    ledger = result.scalars().all()

    return {
        "transactions": [
            {
                "id": str(t.id),
                "amount": float(t.amount),
                "entry_type": t.entry_type,
                "reference_id": t.reference_id,
                "reference_type": t.reference_type,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in ledger
        ],
        "total": len(ledger),
    }
