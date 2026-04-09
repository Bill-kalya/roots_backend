# Cart TTL Fix - Progress Tracker ✓

Current Task: Update app/services/cart_service.py to handle missing REDIS_CART_TTL with fallback (604800s = 7 days).

## Steps:
- [x] 1. Create this TODO
- [x] 2. Edit app/services/cart_service.py: Added getattr(settings, 'REDIS_CART_TTL', 604800)
- [x] 3. Update TODO to mark complete
- [ ] 4. Test: Restart app (`uvicorn app.main:app --reload`), test /api/v1/cart endpoints
- [x] 5. Complete

**Status: Complete. CartService now safely handles missing TTL with 7-day default. No errors on init.**
