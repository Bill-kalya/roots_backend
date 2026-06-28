# TODO

- [x] Inspect `Order` model and identify `Enum(OrderStatus)` binding behavior.
- [x] Fix SQLAlchemy enum binding to use `.value` (lowercase Postgres enum labels) via `values_callable`.
- [ ] Restart app / redeploy.
- [ ] Create a test order and verify `orders.status` stores lowercase labels in Postgres.

