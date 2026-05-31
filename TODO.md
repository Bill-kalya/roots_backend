# TODO

## Password reset flow
- [ ] Add ForgotPasswordRequest and ResetPasswordRequest schemas to `app/schemas/user.py`
- [ ] Add password reset token generation + email sending to `AuthService` in `app/services/auth_service.py`
- [ ] Add `/forgot-password` and `/reset-password` endpoints to `app/api/routes/auth.py`
- [ ] Add ResetPassword screen and route in frontend `../roots/src`
- [ ] Verify forgot-password route/screen exists in frontend; create if missing
- [ ] Run backend compilation checks and frontend build/lint if available

