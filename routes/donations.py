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
    logger.info(f"📨 Incoming donation request from {request.remote_addr}")
    _ensure_cloudinary()

    # ── 1. Extract & validate text fields ────────────────────────────────────
    try:
        email  = validate_email(request.form.get("email"))
        method = validate_method(request.form.get("method"))
        logger.info(f"✅ Validation passed: email={email}, method={method}")
    except ValidationError as exc:
        logger.warning(f"❌ Validation error: {str(exc)}")
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

    logger.info(f"📦 Received {len(raw_files)} file(s)")

    try:
        validated_files = validate_images(raw_files, max_count=Config.MAX_IMAGES)
        logger.info(f"✅ Image validation passed: {len(validated_files)} file(s)")
    except ValidationError as exc:
        logger.warning(f"❌ Image validation error: {str(exc)}")
        return jsonify({"error": str(exc)}), 400

    # ── 3. Upload images to Cloudinary ────────────────────────────────────────
    proof_urls: list[str] = []
    if validated_files:
        try:
            logger.info(f"📤 Uploading {len(validated_files)} image(s) to Cloudinary...")
            upload_result = upload_images(validated_files, folder=Config.CLOUDINARY_FOLDER)
        except Exception as exc:
            logger.exception(f"❌ Cloudinary upload pipeline failed: {exc}")
            return jsonify({"error": "Image upload failed. Please try again."}), 500

        if upload_result.has_errors:
            logger.warning(f"⚠️  Partial upload failure: {upload_result.errors}")

        proof_urls = upload_result.secure_urls
        logger.info(f"✅ Uploaded {len(proof_urls)} image(s) successfully")

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
        logger.info(f"💾 Donation saved — ref={ref_id} mongo_id={result.inserted_id}")
    except PyMongoError as exc:
        logger.exception(f"❌ MongoDB insert failed: {exc}")
        return jsonify({"error": "Database error. Please try again."}), 500

    # ── 5. Send Telegram alert ────────────────────────────────────────────────
    try:
        logger.info(f"📢 Sending Telegram alert for ref={ref_id}...")
        send_donation_alert(
            bot_token=Config.TELEGRAM_BOT_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID,
            donation=donation_doc,
        )
        logger.info(f"✅ Telegram alert sent")
    except Exception as exc:
        logger.error(f"⚠️  Telegram notification failed (non-fatal): {exc}")

    logger.info(f"✅ Donation complete: ref={ref_id}")
    return jsonify({"success": True, "ref_id": ref_id}), 201


# ── POST /api/verify/<ref_id> (admin route) ───────────────────────────────────

@donations_bp.post("/verify/<ref_id>")
def verify_donation(ref_id: str):
    """
    Mark a pending donation as verified (admin only).
    Protect this endpoint with an ADMIN_SECRET header.

    Headers:
        X-Admin-Secret  str  required
    """
    logger.info(f"🔐 Verification request for ref={ref_id}")

    # Simple secret-header guard
    admin_secret = current_app.config.get("ADMIN_SECRET", "")
    provided_secret = request.headers.get("X-Admin-Secret", "")

    if not admin_secret:
        logger.error("❌ ADMIN_SECRET not configured!")
        return jsonify({"error": "Server misconfiguration."}), 500

    if not provided_secret or provided_secret != admin_secret:
        logger.warning(f"❌ Invalid admin secret attempt for ref={ref_id}")
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
        logger.exception(f"❌ MongoDB update failed: {exc}")
        return jsonify({"error": "Database error."}), 500

    if result.matched_count == 0:
        logger.warning(f"❌ No pending donation found: ref={ref_id}")
        return jsonify({"error": f"No pending donation found with ref_id '{ref_id}'."}), 404

    logger.info(f"✅ Donation verified: ref={ref_id}")
    return jsonify({"success": True, "ref_id": ref_id, "status": "verified"}), 200
