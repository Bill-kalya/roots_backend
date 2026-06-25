# TODO: Railway merchant product upload fix

## Goal
Make `POST /api/merchant/products` work on Railway (HTTP 500 currently).

## Step 1 — Disable/handle python-magic + pillow runtime failures
- Check Railway runtime logs for errors like:
  - "python-magic not installed"
  - "pillow not installed"
  - MIME validation failures
- Implement a safe fallback:
  - If python-magic missing, skip magic-based MIME validation (keep extension checks).
  - If pillow missing, skip WEBP conversion (store original extension).

## Step 2 — Ensure dependencies are installed
- Add `python-magic` (and OS libmagic if needed) and `Pillow` to `requirements.txt`.
- Redeploy Railway.

## Step 3 — Ensure uploads are writable
- Verify Railway filesystem/volume for `./uploads`.
- If not writable, mount Railway volume or switch to object storage.

## Step 4 — Validate form payload
- Frontend currently shows "NaN cannot be parsed".
- Verify numeric fields (`price`, `stock`) are valid numbers before sending.

## Step 5 — Confirm
- Re-test merchant upload endpoint.
- Confirm response 201 and uploaded image reachable under `/uploads/<file>`.

