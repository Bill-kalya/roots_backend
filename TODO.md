# TODO

- [x] Implement proper Alembic migrations for `audit_logs` table (replace `pass` with real DDL) in:
  - [x] alembic/versions/df49334632a0_add_audit_logs_table.py
  - [x] alembic/versions/9670021d2cf1_add_audit_logs_table.py
- [x] Make audit-log DB write resilient: catch exceptions in `app/security/audit_log.py` so `/api/auth/register` doesn’t 500 if audit table is missing.
- [x] Run migrations using a reliable command (e.g. `python -m alembic upgrade head`).
- [ ] Re-test `POST /api/auth/register`.



