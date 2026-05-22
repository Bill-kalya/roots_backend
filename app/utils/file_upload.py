from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import re
from typing import Optional

from io import BytesIO


from fastapi import UploadFile, HTTPException

# Local directory served by FastAPI at /uploads
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Keep extensions consistent for StaticFiles and future CDN
ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}

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
    # Collapse multiple dots/spaces artifacts
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


def build_upload_url(filename: str) -> str:
    """Central place to build frontend-consumed relative URL."""
    return f"/uploads/{filename}" 


async def validate_upload_file(
    upload: UploadFile,
    *,
    allowed_extensions: set[str] = ALLOWED_EXTENSIONS,
    allowed_mimes: set[str] = ALLOWED_MIME_TYPES,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
) -> None:
    if upload is None or not getattr(upload, "filename", None):
        raise HTTPException(status_code=400, detail="Missing upload filename")

    if upload.size is not None and upload.size > max_size_bytes:
        raise HTTPException(status_code=400, detail="File too large")


async def _read_prefix(upload: UploadFile, n: int = 2048) -> bytes:
    prefix = await upload.read(n)
    await upload.seek(0)
    return prefix


async def validate_mime_by_magic(upload: UploadFile) -> None:
    """Validate MIME type using python-magic.

    Note: requires `pip install python-magic`.
    """

    try:
        import magic  # type: ignore
    except Exception:
        # If python-magic is not installed, fail closed.
        raise HTTPException(status_code=500, detail="Server misconfiguration: python-magic not installed")

    contents = await _read_prefix(upload, 2048)
    mime = magic.from_buffer(contents, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type")


def maybe_should_convert_to_webp() -> bool:
    # Default: convert everything to webp for performance + CDN friendliness.
    # Can be overridden by env.
    import os

    return os.getenv("UPLOAD_CONVERT_TO_WEBP", "true").lower() in {"1", "true", "yes"}


async def save_upload_image(
    upload: UploadFile,
    *,
    convert_to_webp: Optional[bool] = None,
) -> str:
    """Save an upload to the filesystem with a safe, unique filename.

    Returns:
        filename only (NOT a full URL). Example: <uuid>.webp
    """

    # Validate basic constraints
    if convert_to_webp is None:
        convert_to_webp = maybe_should_convert_to_webp()

    # Hard validation: extension first, then MIME by magic.
    # (We still do extension checks because clients often send .jpg/.png, but we do not trust it alone.)
    safe_ext = _get_extension(upload.filename)

    await validate_mime_by_magic(upload)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    if convert_to_webp:
        try:
            from PIL import Image  # type: ignore
        except Exception:
            raise HTTPException(status_code=500, detail="Server misconfiguration: pillow not installed")

        # Convert using PIL
        # Read all bytes into memory for Pillow.
        data = await upload.read()
        await upload.seek(0)
        image = Image.open(BytesIO(data))  # type: ignore[name-defined]
        # Normalize channels: convert paletted images to RGB(A)
        image = image.convert("RGBA") if image.mode in {"P", "RGBA"} else image.convert("RGB")

        webp_filename = f"{uuid4().hex}.webp"
        out_path = UPLOADS_DIR / webp_filename
        image.save(out_path, "WEBP", quality=85, method=6)
        return webp_filename

    # No conversion: preserve extension, but unique name.
    filename = generate_safe_filename(upload.filename)
    file_path = UPLOADS_DIR / filename

    # Save as bytes (no original name stored)
    # Stream to disk in chunks for large files.
    import shutil
    with file_path.open("wb") as buffer:
        # Ensure we start from beginning
        await upload.seek(0)
        shutil.copyfileobj(upload.file, buffer)

    return filename

