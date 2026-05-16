"""
services/validators.py
========================
Pure validation functions — no Flask imports, easily unit-testable.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

# RFC-5322-lite email regex (covers 99.9 % of real addresses)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

ALLOWED_MIMETYPES: frozenset[str] = frozenset({
    "image/jpeg", "image/png", "image/webp", "image/gif",
})

MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB


class ValidationError(ValueError):
    """Raised when user-supplied data fails validation."""


def validate_email(email: str | None) -> str:
    """Validate and normalize email address."""
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required.")
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValidationError("Invalid email address.")
    return email


def validate_method(method: str | None) -> str:
    """Validate donation method."""
    VALID = {
        "btc", "sol", "usdt",
        "amazon", "apple", "steam", "sephora", "razer",
    }
    if not method or method.strip().lower() not in VALID:
        raise ValidationError(f"method must be one of: {', '.join(sorted(VALID))}.")
    return method.strip().lower()


def validate_images(
    files: list[FileStorage],
    max_count: int = 5,
) -> list[FileStorage]:
    """
    Validate a list of uploaded FileStorage objects.
    Checks:
    - Count ≤ max_count
    - MIME type is an allowed image type
    - File size ≤ MAX_IMAGE_BYTES

    Returns the validated list (unchanged) or raises ValidationError.
    """
    if len(files) > max_count:
        raise ValidationError(f"Maximum {max_count} images allowed.")

    validated: list[FileStorage] = []
    for i, f in enumerate(files, start=1):
        if not f or not f.filename:
            continue  # skip empty slots

        mimetype = f.mimetype or ""
        if mimetype not in ALLOWED_MIMETYPES:
            raise ValidationError(
                f"Image {i} has an unsupported type '{mimetype}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_MIMETYPES))}."
            )

        # Peek at file size without consuming the stream
        f.stream.seek(0, 2)        # seek to end
        size = f.stream.tell()
        f.stream.seek(0)           # reset for later reads

        if size > MAX_IMAGE_BYTES:
            mb = size / (1024 * 1024)
            raise ValidationError(
                f"Image {i} is {mb:.1f} MB. Maximum allowed is 5 MB."
            )

        validated.append(f)

    return validated
