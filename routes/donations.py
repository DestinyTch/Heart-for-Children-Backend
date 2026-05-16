"""
routes/donations.py
====================
POST /api/donate          — accept a donation (multipart/form-data)
POST /api/verify/<ref_id> — admin-only: mark a donation verified
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import PyMongoError

from config import Config
from services.cloudinary_service import init_cloudinary, upload_images
from services.telegram_service import send_donation_alert
from services.validators import ValidationError, validate_email, validate_images, validate_method

logger = logging.getLogger(__name__)
donations_bp = Blueprint("donations", __name__)

_cloudinary_ready = False


def _ensure_cloudinary() -> None:
    global _cloudinary_ready
    if not _cloudinary_ready:
        init_cloudinary(current_app.config)
        _cloudinary_ready = True


def _generate_ref_id(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "HFC-" + "".join(secrets.choice(alphabet) for _ in range(length))


@donations_bp.post("/donate")
def donate():
    logger.info(f"📨 Incoming donation request from {request.remote_addr}")
    _ensure_cloudinary()

    # ── 1. Validate text fields ───────────────────────────────────────────────
    try:
        email  = validate_email(request.form.get("email"))
        method = validate_method(request.form.get("method"))
        logger.info(f"✅ Validation passed: email={email}, method={method}")
    except ValidationError as exc:
        logger.warning(f"❌ Validation error: {exc}")
        return jsonify({"error": str(exc)}), 400

    is_anon = request.form.get("anonymous", "0") == "1"
    name    = "Anonymous" if is_anon else (request.form.get("name", "").strip() or "Anonymous")
    amount  = request.form.get("amount", "").strip() or None
    code    = request.form.get("code", "").strip() or None

    # ── 2. Validate images ────────────────────────────────────────────────────
    raw_files = [request.files[k] for k in request.files if k.startswith("proof_")]
    logger.info(f"📦 Received {len(raw_files)} file(s)")

    try:
        validated_files = validate_images(raw_files, max_count=Config.MAX_IMAGES)
    except ValidationError as exc:
        logger.warning(f"❌ Image validation error: {exc}")
        return jsonify({"error": str(exc)}), 400

    # ── 3. Upload to Cloudinary ───────────────────────────────────────────────
    proof_urls: list[str] = []
    if validated_files:
        try:
            upload_result = upload_images(validated_files, folder=Config.CLOUDINARY_FOLDER)
        except Exception as exc:
            logger.exception(f"❌ Cloudinary upload failed: {exc}")
            return jsonify({"error": "Image upload failed. Please try again."}), 500

        if upload_result.has_errors:
            logger.warning(f"⚠️  Partial upload failure: {upload_result.errors}")

        proof_urls = upload_result.secure_urls
        logger.info(f"✅ Uploaded {len(proof_urls)} image(s)")

    # ── 4. Save to MongoDB ────────────────────────────────────────────────────
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
        result = current_app.db.donations.insert_one(donation_doc)
        logger.info(f"💾 Donation saved — ref={ref_id} id={result.inserted_id}")
    except PyMongoError as exc:
        logger.exception(f"❌ MongoDB insert failed: {exc}")
        return jsonify({"error": "Database error. Please try again."}), 500

    # ── 5. Telegram alert ─────────────────────────────────────────────────────
    try:
        send_donation_alert(
            bot_token=Config.TELEGRAM_BOT_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID,
            donation=donation_doc,
        )
        logger.info("✅ Telegram alert sent")
    except Exception as exc:
        logger.error(f"⚠️  Telegram failed (non-fatal): {exc}")

    logger.info(f"✅ Donation complete: ref={ref_id}")
    return jsonify({"success": True, "ref_id": ref_id}), 201


@donations_bp.post("/verify/<ref_id>")
def verify_donation(ref_id: str):
    logger.info(f"🔐 Verification request for ref={ref_id}")

    admin_secret    = current_app.config.get("ADMIN_SECRET", "")
    provided_secret = request.headers.get("X-Admin-Secret", "")

    if not admin_secret:
        logger.error("❌ ADMIN_SECRET not configured!")
        return jsonify({"error": "Server misconfiguration."}), 500

    if not provided_secret or provided_secret != admin_secret:
        logger.warning(f"❌ Invalid admin secret for ref={ref_id}")
        return jsonify({"error": "Forbidden."}), 403

    try:
        result = current_app.db.donations.update_one(
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
        logger.warning(f"❌ No pending donation: ref={ref_id}")
        return jsonify({"error": f"No pending donation found with ref_id '{ref_id}'."}), 404

    logger.info(f"✅ Donation verified: ref={ref_id}")
    return jsonify({"success": True, "ref_id": ref_id, "status": "verified"}), 200
