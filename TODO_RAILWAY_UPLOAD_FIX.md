# TODO_RAILWAY_UPLOAD_FIX.md

## Steps
- [ ] Update `_normalize_image_url` in `app/api/routes/products.py` to preserve Cloudinary `https://res.cloudinary.com/...` URLs.
- [ ] Keep legacy `/uploads/...` and basename-only normalization for backward compatibility.
- [ ] Run a quick sanity check by starting the app (or running unit/lint if available) and verifying the `/api/products/` payload returns valid Cloudinary URLs.
- [ ] Optionally verify galleries (`gallery`) are normalized consistently with the same rule.

