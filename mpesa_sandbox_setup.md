# M-Pesa Sandbox Setup (Daraja STK Push)

This repo already contains an STK Push initiator:
- `app/services/mpesa_service.py` (`MpesaService.stk_push`)

## 1) Add required environment variables

Add the following keys to your `.env` (do **not** commit real secrets to git):

```env
# --- M-Pesa Daraja sandbox credentials ---
MPESA_CONSUMER_KEY=REPLACE_ME
MPESA_CONSUMER_SECRET=REPLACE_ME

# "Business Short Code" from Daraja sandbox
MPESA_BUSINESS_SHORT_CODE=REPLACE_ME

# "Passkey" from Daraja sandbox
MPESA_PASSKEY=REPLACE_ME

# Daraja token and STK endpoints (Africa sandbox)
MPESA_TOKEN_URL=https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials
MPESA_STK_URL=https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest

# Callback URL for Daraja to POST results to
# Must be publicly reachable via HTTPS.
MPESA_CALLBACK_URL=https://REPLACE_ME/ngrok-or-public-url/mpesa/callback

# Order reference grouping (optional)
MPESA_ACCOUNT_REFERENCE=ROOTS

# Password encoding strategy used by this repo (default is correct for most Daraja sandbox setups)
MPESA_PASSWORD_ENCODING=base64_sha256
```

### About `MPESA_PASSWORD_ENCODING`
This repo defaults to `base64_sha256`, i.e. it computes:
`base64_encode(sha256(shortcode+passkey+timestamp))`

If your Daraja request fails due to “invalid password”, set:
`MPESA_PASSWORD_ENCODING=base64_raw`

## 2) Add/verify callback endpoint

Daraja sends STK Push results to `MPESA_CALLBACK_URL`.
This backend currently has:
- No dedicated Daraja callback router found in `app/api/routes/*`.

So you should implement an endpoint like:
- `POST /mpesa/callback`

that:
1) validates Daraja payload
a) confirms the payment resultCode
b) extracts `CheckoutRequestID` / `MerchantRequestID` / `ResultMetadata`
2) looks up the related `order`
3) updates `Order.status` and `payment_reference`

**Important mapping:**
Your `MpesaService.stk_push()` currently sets:
- `AccountReference = order_reference`

To reconcile callback → order, store `order_reference` as the payment reference you can later match.

If you want matching by UUID `order.id`, set `order_reference` to that UUID string when calling `stk_push`.

## 3) Create a test route (optional)

For local testing, create a temporary debug endpoint that:
- accepts `phone` and `amount`
- creates an `order_reference`
- calls `MpesaService.stk_push(phone, amount, order_reference)`

Then trigger a test STK push and confirm your callback endpoint receives POST.

## 4) Security + efficiency requirements

- `MPESA_CALLBACK_URL` must be HTTPS.
- Use a tunnel (ngrok/cloudflared) for local dev.
- Add request authentication/verification for callback if you implement it.
  - At minimum: validate payload presence and `resultCode`
  - Prefer: verify IP allowlist / signature if your Daraja plan supports it.

## 5) Operational checklist

1. Restart API after updating `.env`.
2. Call the checkout flow that triggers STK push.
3. Confirm callback request arrives.
4. Confirm `orders.status` transitions from `pending` → `paid`.

---

## Notes about this repo

- STK push initiation is implemented.
- Payment confirmation happens via `OrderService.confirm_payment()` in `app/services/order_service.py`.
- This repo does not currently show a Daraja callback handler route; add one.

