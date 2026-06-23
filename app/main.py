from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from redis import asyncio as aioredis
import signal
import asyncio
import logging
from typing import Optional
from datetime import datetime
import uvicorn
import os

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import db_manager
from app.db.migrate import run_migrations
from app.cache.redis_manager import redis_manager
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.circuit_breaker import circuit_breakers
from app.monitoring.health import router as health_router
from app.core.metrics import get_metrics
from app.api.routes import auth, newsletter, testimonials, products as public_products, cart
from app.api.routes.merchant.public import router as merchant_public_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.geo import router as geo_router




from app.api.routes import mpesa
from app.api.routes.payments_paypal import router as paypal_routes
from app.api.routes.orders import router as order_router
from app.api.routes.payments_stripe import router as stripe_routes
from app.api.routes.shipping import router as shipping_router
from app.api.routes.receipts import router as receipts_router








# Role-based route imports
from app.api.routes.user import products as user_products, profile as user_profile, orders as user_orders
from app.api.routes.merchant import products as merchant_products, orders as merchant_orders, analytics as merchant_analytics
from app.api.routes.merchant import payout_settings as merchant_payout_settings
from app.api.routes.admin import dashboard as admin_dashboard, users as admin_users, products as admin_products, settings as admin_settings
from app.api.errors import (
    request_validation_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
    global_exception_handler,
)



logger = logging.getLogger(__name__)

# Setup logging first
setup_logging()

class GracefulShutdown:
    """Handle graceful shutdown of all services"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.background_tasks = []
    
    def signal_handler(self):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal, starting graceful shutdown...")
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self.shutdown_event.wait()
        
        # Give existing requests time to complete
        logger.info("Waiting for existing requests to complete...")
        await asyncio.sleep(5)
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Close connections
        await db_manager.close()
        await redis_manager.close()
        
        logger.info("Graceful shutdown complete")

# Global shutdown handler
shutdown_handler = GracefulShutdown()

# Setup signal handlers
signal.signal(signal.SIGTERM, lambda s, f: shutdown_handler.signal_handler())
signal.signal(signal.SIGINT, lambda s, f: shutdown_handler.signal_handler())

def validate_production_settings():
    """Fail-fast for required production-only M-Pesa configuration."""
    if settings.ENVIRONMENT != "production":
        return

    required = {
        "MPESA_CALLBACK_SECRET": settings.MPESA_CALLBACK_SECRET,
        "MPESA_CONSUMER_KEY": settings.MPESA_CONSUMER_KEY,
        "MPESA_CONSUMER_SECRET": settings.MPESA_CONSUMER_SECRET,
        "MPESA_BUSINESS_SHORT_CODE": settings.MPESA_BUSINESS_SHORT_CODE,
        "MPESA_PASSKEY": settings.MPESA_PASSKEY,
        "MPESA_STK_URL": settings.MPESA_STK_URL,
        "MPESA_TOKEN_URL": settings.MPESA_TOKEN_URL,
        "MPESA_CALLBACK_URL": settings.MPESA_CALLBACK_URL,
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required MPESA production settings: {', '.join(missing)}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enterprise lifecycle management with graceful shutdown"""
    
    # Startup
    logger.info("🚀 Starting Roots Backend - Enterprise Edition with RBAC")
    start_time = datetime.utcnow()
    
    try:
        # 🔥 Fail-fast config validation before migrations
        validate_production_settings()

        # 🔥 RUN MIGRATIONS FIRST
        if os.getenv("SKIP_MIGRATIONS") == "true":
            logger.info("⏭️ Skipping migrations")
        else:
            run_migrations()


        # Initialize connections
        await db_manager.initialize()
        await redis_manager.initialize()
        
        app.state.redis = redis_manager._client  # Expose for middleware
        
        # Start background health monitor
        from app.monitoring.alerts import system_health_monitor
        monitor_task = asyncio.create_task(system_health_monitor())
        shutdown_handler.background_tasks.append(monitor_task)
        
        # Start cart expiration job
        from app.services.cart_service import CartService
        cart_service = CartService(redis_manager._client)
        expiration_task = asyncio.create_task(run_cart_expiration(cart_service))
        shutdown_handler.background_tasks.append(expiration_task)
        
        # Warm up cache
        from app.cache.cache_strategies import cache_warmer
        await cache_warmer.start_warmup()
        
        logger.info(f"✅ All services initialized in {(datetime.utcnow() - start_time).total_seconds():.2f}s")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    await shutdown_handler.wait_for_shutdown()
    logger.info("✅ Shutdown complete")

async def run_cart_expiration(cart_service):
    """Background task for cart expiration"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            expired = await cart_service.expire_carts(older_than_days=7)
            if expired > 0:
                logger.info(f"Expired {expired} abandoned carts")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cart expiration error: {e}")

# Create FastAPI app
app = FastAPI(


    title="Roots API - Enterprise Edition with RBAC",

    version="2.0.0",
    redirect_slashes=True,
    description="Enterprise E-commerce Backend with Role-Based Access Control",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    # Kubernetes readiness/liveness probes
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoints for k8s"},
        {"name": "Authentication", "description": "Auth with MFA support"},
        {"name": "Products", "description": "Product catalog"},
        {"name": "Cart", "description": "Shopping cart operations"},
        {"name": "Orders", "description": "Order management"},
    ]
)

# Register global exception handlers (centralized error responses)
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# Enterprise middleware stack (optimized order)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

# TrustedHostMiddleware: disable strict host validation on Railway because
# internal health probes may use private IP host headers.
if os.getenv("RAILWAY_ENVIRONMENT"):
    # Railway's edge already handles host validation before traffic reaches
    # this container, so we can skip this middleware safely in that environment.
    trusted_hosts = None
elif settings.ENVIRONMENT == "production":
    trusted_hosts = list(settings.TRUSTED_HOSTS)
else:
    trusted_hosts = ["*"]

if trusted_hosts is not None:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
app.add_middleware(RequestIDMiddleware)

# CORS with specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Allow Vercel preview deployments in addition to explicit origins.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
    expose_headers=["X-Request-ID", "X-RateLimit-*", "X-Process-Time"],
    max_age=3600  # Cache preflight requests for 1 hour
)

# Debug endpoint for CORS verification
from app.core.config import settings

@app.get("/debug/cors")
async def debug_cors():
    return {
        "cors_origins": settings.CORS_ORIGINS,
        "type": type(settings.CORS_ORIGINS).__name__,
        "count": len(settings.CORS_ORIGINS)
    }

# Custom middleware for metrics and rate limiting
@app.middleware("http")
async def enterprise_middleware(request: Request, call_next):
    """Combined middleware for metrics, rate limiting, and tracing"""
    
    # Let CORS preflight pass through untouched
    if request.method == "OPTIONS":
        return await call_next(request)
    
    start_time = datetime.utcnow()
    
    # Rate limiting / call downstream middleware/route.
    # IMPORTANT: do not swallow exceptions here; let FastAPI's registered
    # exception handlers format a consistent JSON response.
    response = await rate_limit_middleware(request, call_next)

    # Add processing time header
    process_time = (datetime.utcnow() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)

    # Add security headers

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Content Security Policy: allow Stripe scripts/iframes and the configured API
    try:
        public_api = settings.PUBLIC_API_BASE_URL.rstrip("/")
    except Exception:
        public_api = ""

    csp_parts = [
        "default-src 'self'",
        "script-src 'self' https://js.stripe.com",
        "style-src 'self' 'unsafe-inline'",
        "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
        f"connect-src 'self' {public_api} https://api.stripe.com",
        "img-src 'self' data: https:",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

    # Permissions-Policy: remove deprecated features like ambient-light-sensor
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response

# Kubernetes probes
# Metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint"""
    return await get_metrics()

# Health endpoints
app.include_router(health_router, prefix="/health", tags=["Health"])

# Serve uploaded images from local filesystem.
# This must exist for frontend URLs like /uploads/<filename>.
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")
# Use absolute path for production reliability.
uploads_dir_path = os.path.abspath(UPLOADS_DIR)
try:
    app.mount(
        "/uploads",
        StaticFiles(directory=uploads_dir_path, html=False),
        name="uploads",
    )
    logger.info(f"Static /uploads mounted from: {uploads_dir_path}")
except Exception as e:
    # Fail-soft on misconfiguration so the API can still start.
    logger.error(f"Failed to mount static /uploads from {uploads_dir_path}: {e}")





# ============ PUBLIC ROUTES (No Authentication) ============


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(newsletter.router, prefix="/api/newsletter", tags=["Newsletter"])
app.include_router(testimonials.router, prefix="/api/testimonials", tags=["Testimonials"])
app.include_router(public_products.router, prefix="/api/products", tags=["Public Products"])
app.include_router(merchant_public_router, prefix="/api/merchants", tags=["Public Merchants"])
app.include_router(geo_router, prefix="/api", tags=["Geo"])


# ============ M-PESA (Public) ============
app.include_router(mpesa.router, prefix="/api/payments/mpesa", tags=["M-Pesa"])

# ============ PayPal (Authenticated) ============
app.include_router(paypal_routes, prefix="/api/payments/paypal", tags=["PayPal"])

# ============ Chat (WebSocket) ============

app.include_router(chat_router)

# ============ Orders (Create) ============
# Public create-order endpoint for checkout flow.
# Uses app/api/routes/orders.py where create_order is mounted at @router.post("/" ).
app.include_router(order_router, prefix="/api/orders", tags=["Orders"])

# ============ Shipping (Rates) ============
app.include_router(shipping_router, prefix="/api/shipping", tags=["Shipping"])

# ============ Receipts (Receipt generation/verification) ============
app.include_router(receipts_router)









# ============ USER ROUTES (Authenticated Users) ============

app.include_router(cart.router, prefix="/api/cart", tags=["Cart"])
app.include_router(user_products.router, prefix="/api/user/products", tags=["User - Products"])
app.include_router(user_profile.router, prefix="/api/user/profile", tags=["User - Profile"])
app.include_router(user_orders.router, prefix="/api/user/orders", tags=["User - Orders"])

# ============ MERCHANT ROUTES (Merchant Role Required) ============
app.include_router(merchant_products.router, prefix="/api/merchant/products", tags=["Merchant - Products"])
app.include_router(merchant_orders.router, prefix="/api/merchant/orders", tags=["Merchant - Orders"])
app.include_router(merchant_analytics.router, prefix="/api/merchant/analytics", tags=["Merchant - Analytics"])
app.include_router(merchant_payout_settings.router, prefix="/api/merchant", tags=["Merchant - Payout Settings"])
# NOTE: merchant analytics router provides GET / for /api/merchant/analytics


# ============ ADMIN ROUTES (Admin Role Required) ============
app.include_router(admin_dashboard.router, prefix="/api/admin/dashboard", tags=["Admin - Dashboard"])
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["Admin - Users"])
app.include_router(admin_products.router, prefix="/api/admin/products", tags=["Admin - Products"])
app.include_router(admin_settings.router, prefix="/api/admin/settings", tags=["Admin - Settings"])

@app.get("/")
async def root():
    return {
        "message": "Roots Backend API with RBAC",
        "version": "2.0.0",
        "roles": ["USER", "MERCHANT", "ADMIN"],
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Disable reload in production
        workers=4,  # Multiple workers for production
        loop="uvloop",
        http="httptools",
        log_level=settings.LOG_LEVEL.lower()
    )