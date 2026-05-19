# TODO

- [x] Fix AttributeError in token refresh flow by passing the real `request` into `AuthService.refresh_tokens`.
- [x] Add defensive handling in `AuthService.refresh_tokens` for cases where `request` is None (safe IP/fingerprint extraction).

- [ ] Run a quick lint/test (or start server) and verify `/api/auth/refresh` no longer crashes.
- [ ] (Follow-up) Investigate intermittent DB connection timeout from `get_write_session` pooling/timeouts.

