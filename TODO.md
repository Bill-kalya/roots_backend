- [x] Inspect migration files for duplicate email verification expiry
- [x] Edit alembic/versions/831669f74097_add_email_verification_expiry.py to make it a no-op (upgrade/downgrade are `pass`)
- [ ] Re-run Alembic migration (upgrade head) to confirm no duplicate-column collisions
- [ ] Resolve missing dependency error if encountered during Alembic env load (pythonjsonlogger)

