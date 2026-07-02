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




def _normalize_mpesa_mode(mode: Optional[str]) -> str:
    # Default to PHONE for backward-compatibility.
    if mode == "TILL":
        return "TILL"
    if mode == "POCHI":
        return "POCHI"
    return "PHONE"




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
            mpesa_mode="PHONE",
            mpesa_phone=None,
            mpesa_till_number=None,
            pochi_phone=None,
            paypal_email=None,
            stripe_account_id=None,
            is_verified=False,
            supported_methods=_SUPPORTED_METHODS,
        )


    return MerchantPayoutSettingsResponse(
        payout_method=settings_obj.payout_method,  # type: ignore[arg-type]
        mpesa_mode=getattr(settings_obj, "mpesa_mode", "PHONE"),
        mpesa_phone=settings_obj.mpesa_phone,
        mpesa_till_number=getattr(settings_obj, "mpesa_till_number", None),
        pochi_phone=getattr(settings_obj, "pochi_phone", None),
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
    normalized_till: Optional[str] = None

    # Validate method-specific required fields
    if payload.payout_method == MerchantPayoutMethod.MPESA.value:
        mpesa_mode = _normalize_mpesa_mode(payload.mpesa_mode)

        if mpesa_mode == "PHONE":
            try:
                # mpesa_phone is required when mpesa_mode=PHONE
                normalized_phone = _normalize_phone(payload.mpesa_phone)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                )

        elif mpesa_mode == "TILL":
            # mpesa_till_number is required when mpesa_mode=TILL
            if not payload.mpesa_till_number or not str(payload.mpesa_till_number).strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="mpesa_till_number is required when mpesa_mode is TILL",
                )

            normalized_till = str(payload.mpesa_till_number).strip()
            if not normalized_till.isdigit() or not (5 <= len(normalized_till) <= 10):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Till number must be 5-10 digits",
                )

        elif mpesa_mode == "POCHI":
            # pochi_phone is required when mpesa_mode=POCHI
            normalized_phone = None
            if not getattr(payload, "pochi_phone", None) or not str(payload.pochi_phone).strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="pochi_phone is required when mpesa_mode is POCHI",
                )
            try:
                normalized_phone = _normalize_phone(payload.pochi_phone)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                )

        # Enforce pick-one at API layer as well, for clear errors.
        provided_phone = bool(payload.mpesa_phone and str(payload.mpesa_phone).strip())
        provided_till = bool(payload.mpesa_till_number and str(payload.mpesa_till_number).strip())
        provided_pochi = bool(getattr(payload, "pochi_phone", None) and str(payload.pochi_phone).strip())
        if sum([provided_phone, provided_till, provided_pochi]) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide only one of mpesa_phone, mpesa_till_number, or pochi_phone",
            )


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
        mpesa_mode_db: Optional[str] = None
        mpesa_till_db: Optional[str] = None

        if payload.payout_method == MerchantPayoutMethod.MPESA.value:
            mpesa_mode_db = _normalize_mpesa_mode(payload.mpesa_mode)
            mpesa_till_db = normalized_till

        settings_obj = MerchantPayoutSettings(
            merchant_id=current_user.id,
            payout_method=payload.payout_method,
            mpesa_phone=normalized_phone if payload.payout_method == MerchantPayoutMethod.MPESA.value and (mpesa_mode_db or "PHONE") == "PHONE" else None,
            mpesa_mode=mpesa_mode_db or "PHONE",
            mpesa_till_number=mpesa_till_db if (mpesa_mode_db or "PHONE") == "TILL" else None,
            pochi_phone=normalized_phone if payload.payout_method == MerchantPayoutMethod.MPESA.value and (mpesa_mode_db or "PHONE") == "POCHI" else None,
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
            mpesa_mode_db = _normalize_mpesa_mode(payload.mpesa_mode)
            settings_obj.mpesa_mode = mpesa_mode_db
            settings_obj.mpesa_phone = normalized_phone if mpesa_mode_db == "PHONE" else None
            settings_obj.mpesa_till_number = normalized_till if mpesa_mode_db == "TILL" else None
            settings_obj.pochi_phone = normalized_phone if mpesa_mode_db == "POCHI" else None
            settings_obj.paypal_email = None
            settings_obj.stripe_account_id = None

        elif payload.payout_method == MerchantPayoutMethod.PAYPAL.value:
            settings_obj.mpesa_phone = None
            settings_obj.mpesa_till_number = None
            settings_obj.pochi_phone = None
            settings_obj.paypal_email = payload.paypal_email
            settings_obj.stripe_account_id = None
        elif payload.payout_method == MerchantPayoutMethod.STRIPE.value:
            settings_obj.mpesa_phone = None
            settings_obj.mpesa_till_number = None
            settings_obj.pochi_phone = None
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
    from app.services.wallet_service import WalletService
    ws = WalletService(db)
    wallet = await ws.get_wallet(current_user.id)
    return MerchantEarningsResponse(
        available_balance=float(wallet.available_balance),
        pending_balance=float(wallet.pending_balance),
        currency=wallet.currency,
    )

