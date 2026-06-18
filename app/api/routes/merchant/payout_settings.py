import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import require_merchant
from app.db.session import get_db
from app.models.user import User
from app.models.merchant_payout_settings import MerchantPayoutSettings, MerchantPayoutMethod
from app.schemas.merchant_payout_settings import (
    MerchantPayoutSettingsResponse,
    MerchantPayoutSettingsUpdateRequest,
    MerchantEarningsResponse,
)


router = APIRouter(tags=["Merchant - Payout Settings"])


_SUPPORTED_METHODS = [
    MerchantPayoutMethod.MPESA.value,
    MerchantPayoutMethod.PAYPAL.value,
    MerchantPayoutMethod.STRIPE.value,
]

_PHONE_RE = re.compile(r"^254[71]\d{8}$")


def _normalize_phone(raw: Optional[str]) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("mpesa_phone is required")

    n = raw.strip().replace("+", "").replace(" ", "").replace("-", "")
    if n.startswith("0"):
        n = "254" + n[1:]

    if not _PHONE_RE.match(n):
        raise ValueError("Enter a valid Safaricom number e.g. 0712 345 678")

    return n


@router.get("/payout-settings", response_model=MerchantPayoutSettingsResponse)
async def get_payout_settings(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MerchantPayoutSettings).where(MerchantPayoutSettings.merchant_id == current_user.id)
    result = await db.execute(stmt)
    settings_obj: Optional[MerchantPayoutSettings] = result.scalar_one_or_none()

    if not settings_obj:
        # Default settings record (not persisted) for new merchants.
        return MerchantPayoutSettingsResponse(
            payout_method=MerchantPayoutMethod.MPESA.value,
            mpesa_phone=None,
            paypal_email=None,
            stripe_account_id=None,
            is_verified=False,
            supported_methods=_SUPPORTED_METHODS,
        )

    return MerchantPayoutSettingsResponse(
        payout_method=settings_obj.payout_method,  # type: ignore[arg-type]
        mpesa_phone=settings_obj.mpesa_phone,
        paypal_email=settings_obj.paypal_email,
        stripe_account_id=settings_obj.stripe_account_id,
        is_verified=settings_obj.is_verified,
        supported_methods=_SUPPORTED_METHODS,
    )


@router.put("/payout-settings", response_model=dict)
async def update_payout_settings(
    payload: MerchantPayoutSettingsUpdateRequest,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    if payload.payout_method not in _SUPPORTED_METHODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported payout_method: {payload.payout_method}",
        )

    # NOTE: payout-processing lock not implemented because there's no payout-batch model in current repo.
    # This must be revisited once payout processing state exists.

    normalized_phone: Optional[str] = None
    # Validate method-specific required fields
    if payload.payout_method == MerchantPayoutMethod.MPESA.value:
        try:
            # mpesa_phone is required when selecting MPESA
            normalized_phone = _normalize_phone(payload.mpesa_phone)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    elif payload.payout_method == MerchantPayoutMethod.PAYPAL.value:
        if not getattr(payload, "paypal_email", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="paypal_email is required when payout_method is PAYPAL",
            )
    elif payload.payout_method == MerchantPayoutMethod.STRIPE.value:
        if not getattr(payload, "stripe_account_id", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="stripe_account_id is required when payout_method is STRIPE",
            )

    stmt = select(MerchantPayoutSettings).where(MerchantPayoutSettings.merchant_id == current_user.id)
    result = await db.execute(stmt)
    settings_obj: Optional[MerchantPayoutSettings] = result.scalar_one_or_none()

    if not settings_obj:
        # New settings record: populate fields according to selected method
        settings_obj = MerchantPayoutSettings(
            merchant_id=current_user.id,
            payout_method=payload.payout_method,
            mpesa_phone=normalized_phone if payload.payout_method == MerchantPayoutMethod.MPESA.value else None,
            paypal_email=payload.paypal_email if payload.payout_method == MerchantPayoutMethod.PAYPAL.value else None,
            stripe_account_id=payload.stripe_account_id if payload.payout_method == MerchantPayoutMethod.STRIPE.value else None,
            is_verified=False,
        )
        db.add(settings_obj)
    else:
        # Update fields according to selected method. Only MPESA requires a phone.
        # Reset `is_verified` if merchant changed their payout method.
        if settings_obj.payout_method != payload.payout_method:
            settings_obj.is_verified = False

        settings_obj.payout_method = payload.payout_method
        if payload.payout_method == MerchantPayoutMethod.MPESA.value:
            settings_obj.mpesa_phone = normalized_phone
            settings_obj.paypal_email = None
            settings_obj.stripe_account_id = None
        elif payload.payout_method == MerchantPayoutMethod.PAYPAL.value:
            settings_obj.mpesa_phone = None
            settings_obj.paypal_email = payload.paypal_email
            settings_obj.stripe_account_id = None
        elif payload.payout_method == MerchantPayoutMethod.STRIPE.value:
            settings_obj.mpesa_phone = None
            settings_obj.paypal_email = None
            settings_obj.stripe_account_id = payload.stripe_account_id
        # Keep is_verified as-is for now (backend verification flow may be async later).
        # If you want strict behavior (reset to False on change), switch to: settings_obj.is_verified = False

    await db.commit()
    await db.refresh(settings_obj)

    return {"success": True}


@router.get("/earnings", response_model=MerchantEarningsResponse)
async def get_merchant_earnings(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    # Current repo does not have a payout/ledger/batch model.
    # For Phase 1, return safe defaults (so frontend contract exists and can be wired).
    return MerchantEarningsResponse(
        available_balance=0.0,
        pending_balance=0.0,
        currency="KES",
    )

