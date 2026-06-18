# TODO - Merchant payout settings + earnings contract (backend-first)

## Phase 1 (Implemented next)
- [ ] Add DB model `MerchantPayoutSettings` (merchant_id unique, MPESA-only for now)
- [ ] Add Alembic migration to create `merchant_payout_settings` table
- [ ] Add Pydantic schemas for GET/PUT contract
- [ ] Add merchant-only routes:
  - [ ] GET `/api/merchant/payout-settings` -> returns payout_method/mpesa_phone + supported_methods + is_verified
  - [ ] PUT `/api/merchant/payout-settings` -> validates MPESA phone
- [ ] Add merchant-only route:
  - [ ] GET `/api/merchant/earnings` -> returns available_balance/pending_balance/currency
- [ ] Wire new router in `app/main.py`
- [ ] Export model from `app/models/__init__.py`

## Verification & payout-processing lock
- [ ] Detect existing payout-processing indicator in codebase; otherwise implement safe placeholder behavior

## Testing
- [ ] Run `alembic upgrade head`
- [ ] Start server and manually hit endpoints with curl/postman

