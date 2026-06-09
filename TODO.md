# TODO - CORS + Production fixes

## Plan (approved by repository inspection)

### 1) Fix CORS for Vercel deployments
- Code change: updated `app/main.py` to include `allow_origin_regex=r"https://.*\.vercel\.app"` in `CORSMiddleware`.
- Deployment: still set exact `CORS_ORIGINS` in Railway to include your primary domains (helps keep policy explicit).
  - `CORS_ORIGINS=["https://roots-black.vercel.app","https://roots-gold.vercel.app"]`



### 2) Fix the failing CORS preflight /api/auth/login OPTIONS 400
- Confirm `enterprise_middleware` does not block OPTIONS (it currently early-returns `call_next`).
- If it still fails after CORS env update, inspect the auth login route and any custom endpoint-level OPTIONS handlers.

### 3) Fix testimonials UndefinedTableError
- Run Alembic migrations that create `testimonials` table.
- If unable to migrate immediately: temporarily disable the testimonials endpoint/router to prevent DB query.

