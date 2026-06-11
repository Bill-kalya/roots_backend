# TODO - Fix MFA

- [x] Add server-side MFA challenge storage (Redis) for login step-up.
- [x] Update auth routes to return a challenge id on step 1 and require it on step 2.
- [x] Update Pydantic schemas for MFA challenge id.
- [x] Ensure code verification uses the correct user + challenge state.
- [x] Add/adjust audit logging for MFA step failures.
- [ ] Run basic lint/test commands (if available) and ensure endpoints compile.


