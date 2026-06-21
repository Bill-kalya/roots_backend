# roots_backend

## Railway Deployment Checklist

This repository is already configured for Railway with the following defaults:

- `Procfile` exists: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `runtime.txt` pins `python-3.12.10`
- `requirements.txt` installs dependencies
- `app/main.py` runs Alembic migrations at startup by default

### Required Railway Services

1. PostgreSQL
2. Redis

### Required Railway Environment Variables

Set the following variables in Railway project settings:

- `ENVIRONMENT=production`
- `SECRET_KEY=<strong random secret>`
- `DATABASE_URL=<railway postgres url>`
- `REDIS_URL=<railway redis url>`
- `PUBLIC_API_BASE_URL=https://api.shoproots.africa`
- `SMTP_HOST` (e.g. `smtp.gmail.com`)
- `SMTP_PORT` (e.g. `587`)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `PAYPAL_CLIENT_ID`
- `PAYPAL_CLIENT_SECRET`
- `PAYPAL_MODE=sandbox` or `live`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_BUSINESS_SHORT_CODE`
- `MPESA_PASSKEY`
- `MPESA_TOKEN_URL`
- `MPESA_STK_URL`
- `MPESA_CALLBACK_URL`
- `MPESA_ACCOUNT_REFERENCE=ROOTS`

Optional but recommended:

- `SENTRY_DSN`
- `RECEIPT_SECRET`
- `RESEND_API_KEY`
- `RAILWAY_ENVIRONMENT=true`
- `FAIL_ON_MIGRATION_ERROR=true`
- `SKIP_MIGRATIONS=false`

### Database Notes

- The app accepts `postgres://...` and automatically converts it to `postgresql+asyncpg://`.
- Set `FAIL_ON_MIGRATION_ERROR=true` if you want deployment to fail when Alembic migrations fail.
- You can also run migrations manually with `alembic upgrade head` as a one-off Railway command.

### Redis Notes

- `REDIS_URL` must start with `redis://` or `rediss://`.
- Railway Redis is required for session/cache and rate limiting.

### File Uploads

- The app currently serves uploads from the local `uploads/` folder at `/uploads`.
- Railway filesystem is ephemeral, so local file uploads are not persistent across deploys.
- For production, use external object storage (S3 or similar) and update upload handling accordingly.

### Domain and Webhooks

- Add `api.shoproots.africa` as a Railway custom domain and verify SSL.
- Configure `PUBLIC_API_BASE_URL=https://api.shoproots.africa` in Railway.
- Update Stripe/webhook endpoints and MPESA callback URLs to your production domain.

### Health and Startup

- Health endpoint: `/health`
- Metrics endpoint: `/metrics`
- Start command is already configured via `Procfile`.

### Quick Railway Steps

1. Add PostgreSQL and Redis services in Railway.
2. Set the required env vars.
3. Configure the custom domain `api.shoproots.africa`.
4. Run `alembic upgrade head` or let the app migrate on startup.
5. Deploy and verify `/health`.

