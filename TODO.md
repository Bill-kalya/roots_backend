# TODO

## Alembic migration fix: split FK dependency (Option C)

- [ ] Create a new migration that adds `order_items.product_id -> products.id` FK *after* final merged products head.
- [ ] Edit `alembic/versions/cc01_create_orders_table.py` to remove the FK constraint from `order_items`.
- [ ] Ensure the new FK migration has `down_revision = '4e8c88804689'` so DAG ordering guarantees `products` exists.
- [ ] Verify: `alembic heads`, `alembic history --verbose`, and run `alembic upgrade head` on a fresh/CI DB.

