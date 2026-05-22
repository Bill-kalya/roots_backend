# TODO - FULL PUBLIC IMAGE URL Fix

- [ ] Add PUBLIC_API_BASE_URL setting to `app/core/config.py`
- [ ] Add helper to build full upload URLs
- [x] Update `app/api/routes/merchant/products.py` to store full URLs in `Product.image_url`

- [ ] (Optional) Bump cache versioning if needed
- [ ] Run server + quick smoke test: create product and verify stored `image_url` is full public URL

