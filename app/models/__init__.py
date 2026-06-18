from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.testimonial import Testimonial
from app.models.newsletter import NewsletterSubscriber
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.receipt import Receipt
from app.models.merchant_payout_settings import MerchantPayoutSettings, MerchantPayoutMethod


# Import all models so Base.metadata knows about them
__all__ = [
    "User",
    "Product",
    "Order",
    "OrderItem",
    "Receipt",
    "MerchantPayoutSettings",
    "MerchantPayoutMethod",
    "Testimonial",
    "NewsletterSubscriber",
    "Conversation",
    "Message",
]


