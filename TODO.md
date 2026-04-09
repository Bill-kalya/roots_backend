# Fix ProductService missing get_products_by_tag startup error

## Steps to complete:
- [x] 1. Add `get_products_by_tag` method to app/services/product_service.py ✅
- [x] 2. Fix category caching lambda in app/cache/cache_strategies.py to use proper instance method with db session ✅
- [x] 3. Test server startup: Ctrl+C && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ✅
- [x] 4. Verify logs show cache warming success and no errors ✅

## Status
✅ Startup error fixed! Server should start without AttributeError.
- [x] Plan approved ✅
