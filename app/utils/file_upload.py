from __future__ import annotations

import asyncio
import re
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings


# Keep extensions consistent for future CDN / transformations
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# 5MB default cap
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Danger chars in filenames (we do not store original names, but we still sanitize)
_NON_SAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9._-]")


def sanitize_filename(filename: str) -> str:
    filename = (filename or "").strip()
    filename = _NON_SAFE_CHARS_RE.sub("_", filename)
    filename = filename.strip(".")
    return filename or "file"


def _get_extension(original_filename: str) -> str:
    original_filename = sanitize_filename(original_filename)
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    return ext


def generate_safe_filename(original_filename: str) -> str:
    ext = _get_extension(original_filename)
    return f"{uuid4().hex}{ext}"


async def validate_upload_file(
    upload: UploadFile,
    *,
    allowed_extensions: set[str] = ALLOWED_EXTENSIONS,
    allowed_mimes: set[str] = ALLOWED_MIME_TYPES,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> None:
    if upload is None or not getattr(upload, "filename", None):
        raise HTTPException(status_code=400, detail="Missing upload filename")

    # Extension allowlist (also rejects e.g. .svg, .html, .php).
    _get_extension(upload.filename)

    # Authoritative size enforcement. UploadFile.size is set from the client's
    # Content-Length (attacker-controlled) and is frequently None for multipart
    # uploads, so we stream the file and count bytes ourselves.
    total = 0
    while True:
        chunk = await upload.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            await upload.seek(0)
            raise HTTPException(
                status_code=400,
                detail=f"File too large (max {max_size_bytes // (1024 * 1024)}MB)",
            )
    await upload.seek(0)

    # Magic-byte check (independent of the client-supplied MIME type).
    detected_ext = await _detect_image_type(upload)
    if detected_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File content is not a valid image")

    # Optional deeper MIME inspection when python-magic is installed.
    await validate_mime_by_magic(upload)


async def _detect_image_type(upload: UploadFile) -> Optional[str]:
    """Detect image type from file signature bytes (no external deps).

    Returns the detected extension ('.jpg', '.png', '.webp', '.gif') or None.
    """
    prefix = await upload.read(16)
    await upload.seek(0)

    if prefix.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return ".webp"
    if prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a"):
        return ".gif"
    return None


async def _read_prefix(upload: UploadFile, n: int = 2048) -> bytes:
    prefix = await upload.read(n)
    await upload.seek(0)
    return prefix


async def validate_mime_by_magic(upload: UploadFile) -> None:
    """Validate MIME type using python-magic.

    If python-magic/libmagic isn't installed, we fall back (do not block uploads).
    """

    try:
        import magic  # type: ignore
    except Exception:
        return

    contents = await _read_prefix(upload, 2048)
    mime = magic.from_buffer(contents, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type")


def maybe_should_convert_to_webp() -> bool:
    # Default: true (we still let Cloudinary transform to webp if possible)
    import os

    return os.getenv("UPLOAD_CONVERT_TO_WEBP", "true").lower() in {"1", "true", "yes"}


async def save_upload_image(
    upload: UploadFile,

    *,
    convert_to_webp: Optional[bool] = None,
) -> str:
    """Upload an image to Cloudinary and return a full URL.

    Behavior change:
    - previously: returned filename like <uuid>.webp
    - now: returns Cloudinary URL like https://res.cloudinary.com/.../image.jpg
    """

    if convert_to_webp is None:
        convert_to_webp = maybe_should_convert_to_webp()

    # Hard validation: extension then MIME by magic (if available)
    _get_extension(upload.filename)
    await validate_mime_by_magic(upload)

    # Read bytes once (Cloudinary SDK upload is blocking, so we read in async)
    data = await upload.read()
    await upload.seek(0)

    def _do_upload() -> str:
        import cloudinary
        import cloudinary.uploader

        # Configure once per process
        config: dict = {
            "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
            "api_key": settings.CLOUDINARY_API_KEY,
            "api_secret": settings.CLOUDINARY_API_SECRET,
            "secure": True,
        }
        cname = (settings.CLOUDINARY_CDN_CNAME or "").strip().rstrip("/")
        if cname:
            # Serve media from the custom CDN CNAME (DNS must point at res.cloudinary.com)
            config["cname"] = cname
            config["secure_cname"] = True
        cloudinary.config(**config)


        filename = generate_safe_filename(upload.filename)
        public_id = Path(filename).stem

        upload_options: dict = {
            "public_id": public_id,
            "resource_type": "image",
            "overwrite": True,
        }

        # Quality control + optional forced webp
        # Cloudinary will handle the conversion; we don't do Pillow here.
        if convert_to_webp:
            upload_options["format"] = "webp"
            upload_options["quality"] = 85

        # Cloudinary accepts file-like objects
        upload_result = cloudinary.uploader.upload(
            BytesIO(data),
            **upload_options,
        )

        # The SDK returns metadata incl. secure_url
        res = upload_result


        secure_url = res.get("secure_url")
        if not secure_url:
            raise HTTPException(status_code=500, detail="Cloudinary upload did not return a URL")
        return secure_url

    try:
        return await asyncio.to_thread(_do_upload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not upload image: {e}")

