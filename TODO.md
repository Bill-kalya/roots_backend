# TODO - Payment Orchestration Layer (Daraja + PayPal)

## Steps
- [x] Understand repo payment gap (orders/inventory exist; payment layer + models/webhooks/routes are missing)
- [x] Create `app/models/payment.py` with `Payment` table
- [x] Extend `app/models/order.py` with payment fields (`payment_provider`, `payment_reference`, `paid_at`) and missing cancellation fields used by service

- [ ] Implement `app/services/mpesa_service.py` (STK Push)
- [ ] Implement `app/services/paypal_service.py` (PayPal Order API + capture if needed)
- [ ] Implement `app/services/payment_service.py` (idempotency + webhook finalization)
- [ ] Harden `OrderService.confirm_payment()` for idempotency + atomic transaction semantics
- [ ] Add `app/api/routes/payments.py` (initiate mpesa/paypal)
- [ ] Add `app/api/routes/webhooks.py` (M-Pesa callback + PayPal webhook verification)
- [ ] Wire new routers into `app/main.py`
- [ ] Extend `app/core/config.py` with required MPesa/PayPal/webhook environment variables
- [ ] Add/adjust schema(s) as needed for payment responses
- [ ] Add required dependencies in `requirements.txt`
- [ ] Create and run Alembic migrations
- [ ] Manual test flow: create order → initiate payment → webhook → verify paid + inventory + fulfillment exactly-once


