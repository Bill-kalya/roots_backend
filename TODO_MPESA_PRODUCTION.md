# TODO - Make M-Pesa Production-Grade (No Business Logic Changes)

## 1) Non-optional callback verification
- [ ] Update `app/main.py` (or settings validation) to fail-fast on startup when `ENVIRONMENT=production` and `MPESA_CALLBACK_SECRET` is missing.
- [ ] Optionally enforce also presence of MPESA token/STK URLs and credentials in production.

## 2) Durable idempotency at DB level
- [ ] Add DB-level uniqueness for callback events.
  - Prefer: use `checkout_request_id` as the immutable key (it already exists as `UNIQUE` on `payments.checkout_request_id`).
  - Additionally: create a *separate* table (or columns) for callback receipts if needed, with `UNIQUE` constraint.
- [ ] Ensure callback handler does not process if the event key already exists in the idempotency store.

## 3) Replay-safe callback processing logic
- [ ] Modify `/api/payments/mpesa/callback` to treat callbacks as untrusted + replayable.
- [ ] Ensure settlement side effects (order confirm + fulfillment queue) run exactly once per immutable event.

## 4) Logging/PII hardening
- [ ] Remove or downgrade full STK payload logging in `app/services/mpesa_service.py`.
- [ ] Stop persisting full callback JSON in `payment.raw_payload` in production; store only sanitized fields.

## 5) Minimal test plan
- [ ] Add a small integration test (or script) that simulates duplicate callbacks and asserts order is paid once.
- [ ] Add a test for callback authentication failure when secret is missing.

## Execution order
1. Fail-fast config.
2. Logging hardening.
3. Durable idempotency.
4. Replay-safe callback settlement.
5. Tests.

