"""
services/cloudinary_service.py
================================
Handles all Cloudinary interactions.
- Configures the SDK once from Flask app config.
- Uploads a list of FileStorage objects sequentially and returns their secure URLs.
- Returns a typed result object so callers can distinguish success from failure.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cloudinary
import cloudinary.uploader

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


def init_cloudinary(app_config) -> None:
    """Call once during app initialisation to configure the Cloudinary SDK."""
    cloudinary.config(
        cloud_name=app_config.CLOUDINARY_CLOUD_NAME,
        api_key=app_config.CLOUDINARY_API_KEY,
        api_secret=app_config.CLOUDINARY_API_SECRET,
        secure=True,           # always use HTTPS URLs
    )
    logger.info("Cloudinary configured — cloud: %s", app_config.CLOUDINARY_CLOUD_NAME)


@dataclass
class UploadResult:
    secure_urls: list[str] = field(default_factory=list)
    public_ids:  list[str] = field(default_factory=list)
    errors:      list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def upload_images(
    files: list[FileStorage],
    folder: str,
) -> UploadResult:
    """
    Upload each FileStorage image to Cloudinary sequentially.

    Args:
        files:  List of validated Werkzeug FileStorage objects.
        folder: Cloudinary folder path (e.g. 'hearts_for_children/proofs').

    Returns:
        UploadResult with secure_urls for every successful upload.
    """
    result = UploadResult()

    for idx, file in enumerate(files):
        try:
            # Read bytes so we can re-seek if needed; avoid temp files on disk.
            raw = file.read()
            response = cloudinary.uploader.upload(
                io.BytesIO(raw),
                folder=folder,
                resource_type="image",
                # Auto-generate a unique public_id; no overwriting existing proofs.
                unique_filename=True,
                overwrite=False,
            )
            secure_url = response["secure_url"]
            public_id  = response["public_id"]
            result.secure_urls.append(secure_url)
            result.public_ids.append(public_id)
            logger.info("Uploaded proof image %d → %s", idx + 1, public_id)

        except cloudinary.exceptions.Error as exc:
            msg = f"Cloudinary upload failed for image {idx + 1}: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected error uploading image {idx + 1}: {exc}"
            logger.exception(msg)
            result.errors.append(msg)

    return result
