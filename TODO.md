# TODO - Fix MFA

- [ ] Add server-side MFA challenge storage (Redis) for login step-up.
- [ ] Update auth routes to return a challenge id on step 1 and require it on step 2.
- [ ] Update Pydantic schemas for MFA challenge id.
- [ ] Ensure code verification uses the correct user + challenge state.
- [ ] Add/adjust audit logging for MFA step failures.
- [ ] Run basic lint/test commands (if available) and ensure endpoints compile.

