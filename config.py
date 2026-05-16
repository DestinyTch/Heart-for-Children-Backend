"""
config.py — Application configuration
All secrets are loaded from environment variables (never hard-coded).
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root


class Config:
    # ── Flask ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str = os.environ["MONGO_URI"]          # required — will raise if missing

    # ── Cloudinary ────────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = os.environ["CLOUDINARY_CLOUD_NAME"]
    CLOUDINARY_API_KEY: str    = os.environ["CLOUDINARY_API_KEY"]
    CLOUDINARY_API_SECRET: str = os.environ["CLOUDINARY_API_SECRET"]
    CLOUDINARY_FOLDER: str     = os.environ.get("CLOUDINARY_FOLDER", "hearts_for_children/proofs")

    # ── Telegram ──────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
    TELEGRAM_CHAT_ID: str   = os.environ["TELEGRAM_CHAT_ID"]

    # ── Admin ─────────────────────────────────────────────────────────────────
    # FIX: was never declared here, so current_app.config.get("ADMIN_SECRET")
    # always returned "" → verify endpoint always 500'd with "Server misconfiguration".
    ADMIN_SECRET: str = os.environ.get("ADMIN_SECRET", "")

    # ── CORS ──────────────────────────────────────────────────────────────────
    # FIX 1: os.environ.get() returns None when var is absent; None.split()
    #         crashes the app before CORS is ever configured.
    # FIX 2: .env had the full page URL with path + trailing slash
    #         (https://destinytch.github.io/Heart-for-Children/).
    #         Browsers send ONLY scheme+host as the Origin header
    #         (https://destinytch.github.io), so Flask-CORS never matched
    #         → ACAO header was never added → browser blocked every request.
    #         rstrip("/") normalises both cases reliably.
    _origins_raw: str = os.environ.get("ALLOWED_ORIGINS", "")
    ALLOWED_ORIGINS: list[str] = [
        o.strip().rstrip("/")
        for o in _origins_raw.split(",")
        if o.strip()
    ]

    # ── Upload constraints ────────────────────────────────────────────────────
    MAX_IMAGES: int       = 5
    MAX_IMAGE_BYTES: int  = 5 * 1024 * 1024          # 5 MB per image
    ALLOWED_MIMETYPES: frozenset = frozenset({
        "image/jpeg", "image/png", "image/webp", "image/gif",
    })
