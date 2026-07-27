from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.db.session import get_db
from app.models.merchant_wallet import MerchantWallet
from app.models.user import User

router = APIRouter()


@router.get("/overview")
async def admin_wallet_overview(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated wallet overview for admin."""
    total_balance = await db.scalar(
        select(func.coalesce(func.sum(MerchantWallet.available_balance), 0))
    ) or 0
    total_pending = await db.scalar(
        select(func.coalesce(func.sum(MerchantWallet.pending_balance), 0))
    ) or 0
    total_earned = await db.scalar(
        select(func.coalesce(func.sum(MerchantWallet.total_earned), 0))
    ) or 0
    total_withdrawn = await db.scalar(
        select(func.coalesce(func.sum(MerchantWallet.total_withdrawn), 0))
    ) or 0
    total_wallets = await db.scalar(select(func.count()).select_from(MerchantWallet)) or 0

    return {
        "total_balance": float(total_balance),
        "total_pending": float(total_pending),
        "total_earned": float(total_earned),
        "total_withdrawn": float(total_withdrawn),
        "total_wallets": int(total_wallets),
    }


@router.get("/merchants")
async def admin_merchant_wallets(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
):
    """List all merchant wallets for admin overview."""
    stmt = (
        select(MerchantWallet)
        .order_by(MerchantWallet.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    wallets = result.scalars().all()

    total = await db.scalar(select(func.count()).select_from(MerchantWallet)) or 0

    return {
        "wallets": [
            {
                "merchant_id": str(w.merchant_id),
                "available_balance": float(w.available_balance),
                "pending_balance": float(w.pending_balance),
                "total_earned": float(w.total_earned),
                "total_withdrawn": float(w.total_withdrawn),
                "currency": w.currency,
            }
            for w in wallets
        ],
        "total": int(total),
    }
