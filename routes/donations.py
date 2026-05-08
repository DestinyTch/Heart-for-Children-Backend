"""
routes/donations.py
====================
POST /api/donate   — accept a donation (multipart/form-data)
POST /api/verify/<ref_id> — admin-only: mark a donation verified
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import PyMongoError

from app import mongo
from config import Config
from services.cloudinary_service import init_cloudinary, upload_images
from services.telegram_service import send_donation_alert
from services.validators import ValidationError, validate_email, validate_images, validate_method

logger = logging.getLogger(__name__)
donations_bp = Blueprint("donations", __name__)

_cloudinary_ready = False  # initialised lazily on first request


def _ensure_cloudinary() -> None:
    global _cloudinary_ready
    if not _cloudinary_ready:
        init_cloudinary(current_app.config)
        _cloudinary_ready = True


def _generate_ref_id(length: int = 10) -> str:
    """Returns a human-readable reference like HFC-A3X9KZ."""
    alphabet = string.ascii_uppercase + string.digits
    return "HFC-" + "".join(secrets.choice(alphabet) for _ in range(length))


# ── POST /api/donate ──────────────────────────────────────────────────────────

@donations_bp.post("/donate")
def donate():
    """
    Accept a donation submission.

    Form fields (multipart/form-data):
        email      str  required
        name       str  optional  (defaults to 'Anonymous')
        anonymous  str  '1' = anonymous, '0' = show name
        method     str  required  (btc | sol | usdt | amazon | apple | steam | sephora | razer)
        amount     str  optional  gift-card face value
        code       str  optional  gift-card code

    Files (optional, up to 5):
        proof_0 … proof_4

    Returns:
        201  { "success": true, "ref_id": "HFC-XXXXXXXXXX" }
        400  { "error": "<validation message>" }
        500  { "error": "Internal server error." }
    """
    _ensure_cloudinary()

    # ── 1. Extract & validate text fields ────────────────────────────────────
    try:
        email  = validate_email(request.form.get("email"))
        method = validate_method(request.form.get("method"))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    is_anon = request.form.get("anonymous", "0") == "1"
    name    = "Anonymous" if is_anon else (request.form.get("name", "").strip() or "Anonymous")
    amount  = request.form.get("amount", "").strip() or None
    code    = request.form.get("code", "").strip() or None

    # ── 2. Collect & validate uploaded image files ────────────────────────────
    raw_files = [
        request.files[key]
        for key in request.files
        if key.startswith("proof_")
    ]

    try:
        validated_files = validate_images(raw_files, max_count=Config.MAX_IMAGES)
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    # ── 3. Upload images to Cloudinary ────────────────────────────────────────
    proof_urls: list[str] = []
    if validated_files:
        try:
            upload_result = upload_images(validated_files, folder=Config.CLOUDINARY_FOLDER)
        except Exception as exc:
            logger.exception("Cloudinary upload pipeline failed: %s", exc)
            return jsonify({"error": "Image upload failed. Please try again."}), 500

        if upload_result.has_errors:
            # Partial failure: log it but proceed with whatever succeeded.
            logger.warning("Some images failed to upload: %s", upload_result.errors)

        proof_urls = upload_result.secure_urls

    # ── 4. Persist donation to MongoDB ────────────────────────────────────────
    ref_id = _generate_ref_id()
    donation_doc = {
        "ref_id":     ref_id,
        "email":      email,
        "name":       name,
        "anonymous":  is_anon,
        "method":     method,
        "amount":     amount,
        "code":       code,
        "proof_urls": proof_urls,
        "status":     "pending",
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = mongo.db.donations.insert_one(donation_doc)
        logger.info("Donation saved — ref=%s mongo_id=%s", ref_id, result.inserted_id)
    except PyMongoError as exc:
        logger.exception("MongoDB insert failed: %s", exc)
        return jsonify({"error": "Database error. Please try again."}), 500

    # ── 5. Send Telegram alert ────────────────────────────────────────────────
    try:
        send_donation_alert(
            bot_token=Config.TELEGRAM_BOT_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID,
            donation=donation_doc,
        )
    except Exception as exc:  # noqa: BLE001  — notification failure must not block the response
        logger.error("Telegram notification failed (non-fatal): %s", exc)

    return jsonify({"success": True, "ref_id": ref_id}), 201


# ── POST /api/verify/<ref_id> (admin route) ───────────────────────────────────

@donations_bp.post("/verify/<ref_id>")
def verify_donation(ref_id: str):
    """
    Mark a pending donation as verified (admin only).
    Protect this endpoint with an ADMIN_SECRET header in production.

    Headers:
        X-Admin-Secret  str  required
    """
    # Simple secret-header guard — replace with JWT or OAuth in production.
    admin_secret = current_app.config.get("ADMIN_SECRET", "")
    if not admin_secret or request.headers.get("X-Admin-Secret") != admin_secret:
        return jsonify({"error": "Forbidden."}), 403

    try:
        result = mongo.db.donations.update_one(
            {"ref_id": ref_id, "status": "pending"},
            {"$set": {
                "status":      "verified",
                "verified_at": datetime.now(timezone.utc),
            }},
        )
    except PyMongoError as exc:
        logger.exception("MongoDB update failed: %s", exc)
        return jsonify({"error": "Database error."}), 500

    if result.matched_count == 0:
        return jsonify({"error": f"No pending donation found with ref_id '{ref_id}'."}), 404

    logger.info("Donation verified — ref=%s", ref_id)
    return jsonify({"success": True, "ref_id": ref_id, "status": "verified"}), 200
