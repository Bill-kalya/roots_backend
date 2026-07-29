import time
import httpx
import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


class MpesaService:
    """M-Pesa Daraja STK Push integration (STK Push initiation)."""

    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.business_short_code = settings.MPESA_BUSINESS_SHORT_CODE
        self.passkey = settings.MPESA_PASSKEY
        self.stk_url = settings.MPESA_STK_URL
        self.token_url = settings.MPESA_TOKEN_URL
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.account_reference = settings.MPESA_ACCOUNT_REFERENCE
        self.transaction_type = settings.MPESA_TRANSACTION_TYPE


        if not self.stk_url or not self.token_url:
            logger.warning("MPESA_STK_URL / MPESA_TOKEN_URL not set")

    async def _generate_token(self) -> str:
        if not self.consumer_key or not self.consumer_secret:
            raise RuntimeError("MPESA_CONSUMER_KEY/MPESA_CONSUMER_SECRET not configured")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                self.token_url,
                auth=(self.consumer_key, self.consumer_secret),
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError(f"MPesa token missing in response: {data}")
            return token

    async def stk_push(self, phone: str, amount: str, order_reference: str) -> dict:
        """Initiate STK Push. Returns provider JSON response."""
        if not phone:
            raise ValueError("mpesa phone is required")
        if not amount:
            raise ValueError("amount is required")
        if not self.business_short_code or not self.passkey:
            raise RuntimeError("MPESA_BUSINESS_SHORT_CODE/MPESA_PASSKEY not configured")
        if not self.callback_url:
            raise RuntimeError("MPESA_CALLBACK_URL not configured")

        token = await self._generate_token()
        timestamp = time.strftime("%Y%m%d%H%M%S")

        # Daraja password = base64encode(ShortCode + Passkey + Timestamp)
        # NOTE: Passkey must be EXACT (no quotes/spaces/newlines in env).
        password_raw = f"{self.business_short_code}{self.passkey}{timestamp}"
        import base64
        password = base64.b64encode(password_raw.encode("utf-8")).decode("utf-8")



        payload = {
            "BusinessShortCode": self.business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.transaction_type,
            "Amount": amount,
            "PartyA": phone,
            "PartyB": self.business_short_code,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": order_reference,
            "TransactionDesc": "Checkout Payment",
        }

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.stk_url, json=payload, headers=headers)
            import json

            resp_text = resp.text
            # Log at DEBUG level and mask phone to avoid PII in production logs.
            masked_phone = phone[:6] + "****" if phone and len(phone) > 6 else phone
            logger.debug("STK push sent phone=%s amount=%s", masked_phone, amount)
            logger.debug(
                "Safaricom response status=%s", resp.status_code
            )

            resp.raise_for_status()
            return resp.json()


