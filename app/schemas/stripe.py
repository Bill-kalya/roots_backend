from uuid import UUID

from pydantic import BaseModel


class StripeIntentRequest(BaseModel):
    order_id: UUID


class StripeIntentResponse(BaseModel):
    client_secret: str

