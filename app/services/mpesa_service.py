import os
import time
import httpx
import logging

logger = logging.getLogger(__name__)


class MpesaService:
    """M-Pesa Daraja STK Push integration (STK Push initiation)."""

    def __init__(self):
        self.consumer_key = os.getenv("MPESA_CONSUMER_KEY")
        self.consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
        self.business_short_code = os.getenv("MPESA_BUSINESS_SHORT_CODE")
        self.passkey = os.getenv("MPESA_PASSKEY")
        self.stk_url = os.getenv("MPESA_STK_URL")
        self.token_url = os.getenv("MPESA_TOKEN_URL")
        self.callback_url = os.getenv("MPESA_CALLBACK_URL")
        self.account_reference = os.getenv("MPESA_ACCOUNT_REFERENCE", "ROOTS")

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

        password = f"{self.business_short_code}{self.passkey}{timestamp}"
        # Daraja requires password base64-encoded; leaving as-is unless env provides encoding.
        # Most deployments base64 the SHA256? We require explicit MPESA_PASSWORD_ENCODING strategy.
        password_encoding = os.getenv("MPESA_PASSWORD_ENCODING", "base64_sha256")
        if password_encoding == "base64_sha256":
            import base64
            import hashlib

            password = base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()
        else:
            # Default: base64 raw concatenation
            import base64

            password = base64.b64encode(password.encode()).decode()

        payload = {
            "BusinessShortCode": self.business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
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
            resp.raise_for_status()
            return resp.json()

