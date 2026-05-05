# Fix Products Table Missing Error - Alembic Migration & Startup Robustness

## Status: 🟡 In Progress (Approved Plan)

### Completed (✅)
1. **Diagnosis**: Confirmed no products migration despite model existing. Startup runs alembic (users only) → queries fail in cache warmup/ProductService.get_featured_products().

### Todo Steps
2. **Generate Alembic Migration** ✅ `f64c3e7ae9d2_create_products_table.py` created
3. **Inspect & Edit Migration** ✅ Table already exists (manual previously) → removed create from migration.
4. **Apply Migration** ✅ Success (now at head f64c3e7ae9d2).
5. **Verify Table** ✅ Exists (duplicate error confirmed).
6. **Test Startup** ✅ Server running http://127.0.0.1:8000, no errors.
7. **Sample Data**: Run `python init_enterprise_db.py`.
8. **Test Endpoint**: `curl http://localhost:8000/api/products/featured`.
9. **attempt_completion**.
9. **Add Sample Data**: Run `python init_enterprise_db.py`
10. **Test Endpoint**: `curl http://localhost:8000/api/products/featured`
11. **attempt_completion**: Confirm fixed.

## Status: 🟡 Verifying All Tables (User Request)

**Products**: ✅ Exists + query works.

**Checking**: testimonials, newsletter, orders, roles.

**Alembic history + endpoints below**.


