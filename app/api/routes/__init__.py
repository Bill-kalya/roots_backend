from app.api.routes.auth import router as auth_router
from app.api.routes.products import router as products_router
from app.api.routes.cart import router as cart_router
from app.api.routes.orders import router as orders_router
from app.api.routes.testimonials import router as testimonials_router
from app.api.routes.newsletter import router as newsletter_router

__all__ = [
    "auth_router",
    "products_router",
    "cart_router",
    "orders_router",
    "testimonials_router",
    "newsletter_router"
]