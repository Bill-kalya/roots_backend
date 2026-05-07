# TODO - MFA end-to-end wiring

## Step 1: Add/adjust MFA schemas
- [ ] Update `app/schemas/user.py` with request/response models:
  - login step1 response including `requires_mfa` + `user_id`
  - `MFASecondStepRequest` for `/api/auth/login/verify-mfa`
  - `MFASetupResponse` and `MFAEnableEnrollRequest`

## Step 2: Implement MFA routes
- [ ] Update `app/api/routes/auth.py`:
  - [ ] Add `POST /mfa/setup`
  - [ ] Add `POST /mfa/verify-enroll`
  - [ ] Add `POST /login/verify-mfa`
  - [ ] Update `POST /login` to return `requires_mfa/user_id` when MFA required

## Step 3: Ensure route wiring
- [ ] Verify `app/main.py` already includes `auth.router` (it does) and no extra changes needed.

## Step 4: Basic smoke tests
- [ ] Run unit/smoke checks by importing FastAPI app and ensuring routes register.

## Step 5: Frontend guidance
- [ ] Provide exact frontend call flow and payloads based on the implemented contract.

