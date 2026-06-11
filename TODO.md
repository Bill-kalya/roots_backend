# TODO

- [x] Update `app/api/routes/auth.py` so `/register` does NOT return a full `UserResponse` as a “completed registration”. Instead returns `{ success: true, requires_email_verification: true }`.
- [ ] (Optional hardening) Update `app/core/dependencies.py` `get_current_user` to also require `User.is_verified == True` (not just `is_active == True`).
- [ ] Add/verify tests or manual steps:
  - [ ] Register with new email
  - [ ] Confirm login returns 401 / “Please verify your email before logging in”
  - [ ] Confirm protected endpoints return 401 until verified
  - [ ] Verify email via `/verify-email?token=...`
  - [ ] Confirm login and protected endpoints work after verification

