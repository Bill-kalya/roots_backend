import os
import httpx
import logging

logger = logging.getLogger(__name__)


class PayPalService:
    """PayPal Checkout integration (creates + captures PayPal order)."""


    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        self.base_url = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

        if not self.client_id or not self.client_secret:
            logger.warning("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET not set")

    async def _get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PayPal credentials not configured")

        auth = httpx.BasicAuth(self.client_id, self.client_secret)
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=auth,
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError(f"PayPal token missing in response: {data}")
            return token

    async def create_order(
        self,
        total_amount: str,
        currency: str,
        intent: str = "CAPTURE",
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        # PayPal Orders v2 payload
        payload = {
            "intent": intent,
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": str(total_amount),
                    }
                }
            ],
            "application_context": {
                "return_url": return_url or os.getenv("PAYPAL_RETURN_URL", "http://localhost"),
                "cancel_url": cancel_url or os.getenv("PAYPAL_CANCEL_URL", "http://localhost"),
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract approval URL
        approval_url = None
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break

        return {
            "paypal_order_id": data.get("id"),
            "approval_url": approval_url,
            "raw": data,
        }

    async def capture_order(self, paypal_order_id: str) -> dict:
        """Capture a PayPal order and return capture info."""
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders/{paypal_order_id}/capture",
                headers=headers,
                json={},
            )
            resp.raise_for_status()
            data = resp.json()

        # Look for the primary capture
        capture_id = None
        capture_status = None
        amount_value = None
        currency_code = None

        # Typical structure: { "status": "COMPLETED", "purchase_units": [ { "payments": [ { "captures": [ ... ] } ] } ] }
        for pu in data.get("purchase_units", []) or []:
            for payment in pu.get("payments", []) or []:
                for cap in payment.get("captures", []) or []:
                    capture_id = cap.get("id") or capture_id
                    capture_status = cap.get("status") or capture_status
                    amount = cap.get("amount") or {}
                    amount_value = amount.get("value") or amount_value
                    currency_code = amount.get("currency_code") or currency_code

        # Fallback to top-level status
        if not capture_status:
            capture_status = data.get("status")

        return {
            "paypal_order_id": paypal_order_id,
            "capture_id": capture_id or data.get("id"),
            "capture_status": capture_status,
            "amount": amount_value,
            "currency": currency_code,
            "raw": data,
        }


