# TODO (blackboxai)

- [ ] Create Alembic migration to add `pochi_phone` column to `merchant_payout_settings`.
- [ ] Update SQLAlchemy model `MerchantPayoutSettings` to include `pochi_phone`.
- [ ] Update Pydantic schema `MerchantPayoutSettingsResponse` and `MerchantPayoutSettingsUpdateRequest` to support `mpesa_mode=POCHI` and `pochi_phone` validation.
- [ ] Update route `app/api/routes/merchant/payout_settings.py` to read/write `pochi_phone` based on selected `mpesa_mode`.
- [ ] Search for frontend `MerchantPayoutSettings.jsx` and update it to allow selecting `POCHI` and sending `pochi_phone`.
- [ ] Locate Daraja disbursement/payout execution code and branch by `mpesa_mode` (PHONE/TILL/POCHI).
- [ ] Run formatting/lint/tests if available.
- [ ] Run a quick smoke test via API calls for all 3 MPESA modes.

