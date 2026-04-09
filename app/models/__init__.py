from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.testimonial import Testimonial
from app.models.newsletter import NewsletterSubscriber

# Import all models so Base.metadata knows about them
__all__ = [
    "User",
    "Product", 
    "Order",
    "OrderItem",
    "Testimonial",
    "NewsletterSubscriber"
]