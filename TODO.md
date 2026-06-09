## Migration fix: duplicate payment columns

- [ ] Update migration 13b29a22f72c to be idempotent for payment columns (skip if column exists)
- [ ] Remove duplicate add_column calls from migration 62c1dea2e853 (upgrade only)
- [ ] Make 62c1dea2e853 downgrade safe/non-destructive (remove audit_logs create and column drops)
- [ ] Run Alembic checks locally: alembic heads, alembic upgrade head, alembic current
- [ ] Commit and push
