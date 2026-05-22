# Image URL Fix Steps

- [ ] Add PUBLIC_API_BASE_URL to app/core/config.py (missing setting)
- [ ] Verify merchant image_url building uses that setting and URL-encodes filenames
- [ ] Audit DB records for trailing spaces / missing extensions (one-time SQL)
- [ ] Locate frontend code in this workspace (or separate repo) that builds <img src> and patch to prepend backend origin via a getImageUrl() helper
- [ ] Run backend + smoke test image URLs

