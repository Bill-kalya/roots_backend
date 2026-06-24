# Task TODO (blackboxai)

## MPESA + Receipts Integrity Fix (priority)
- [x] Create task TODO scaffold
- [x] Fix MPESA callback PaymentStatus comparisons (string vs Enum).
- [x] Standardize MPESA amount reconciliation using Decimal.
- [x] Generate signed Receipt after MPESA callback confirms order payment.
- [x] Make Receipt generation endpoint safe (restrict POST /generate).
- [x] Ensure callback persists Payment updates even if receipt generation errors (receipt should be idempotent/retriable).


## After MPESA passes
- [ ] Run quick sanity checks by starting server and hitting stk-push/callback/receipt verify endpoints.

