from __future__ import annotations

from app.core.config import settings


_CLOUDINARY_HOST = "https://res.cloudinary.com"


def rewrite_image_cdn(url: str) -> str:
    """Rewrite res.cloudinary.com URLs to the custom CDN CNAME when configured.

    Returns the URL unchanged when no CNAME is set, the URL is not a
    Cloudinary URL, or there is nothing to rewrite.
    """
    cname = (settings.CLOUDINARY_CDN_CNAME or "").strip().rstrip("/")
    if not cname or not url or not url.startswith(_CLOUDINARY_HOST):
        return url
    path = url[len(_CLOUDINARY_HOST):]
    return f"https://{cname}{path}"
