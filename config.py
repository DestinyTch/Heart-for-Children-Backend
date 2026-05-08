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

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list in .env, e.g. https://heartsforchildren.org,https://www.heartsforchildren.org
    _origins_raw: str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:5500")
    ALLOWED_ORIGINS: list[str] = [o.strip() for o in _origins_raw.split(",") if o.strip()]

    # ── Upload constraints ────────────────────────────────────────────────────
    MAX_IMAGES: int       = 5
    MAX_IMAGE_BYTES: int  = 5 * 1024 * 1024          # 5 MB per image
    ALLOWED_MIMETYPES: frozenset = frozenset({
        "image/jpeg", "image/png", "image/webp", "image/gif",
    })
