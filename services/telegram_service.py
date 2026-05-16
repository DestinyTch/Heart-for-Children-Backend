"""
services/telegram_service.py
==============================
Sends real-time donation alerts to a Telegram chat.

Behaviour
---------
* Text-only donation  → single sendMessage with formatted Markdown.
* Donation with proofs → sendMessage first, then sendMediaGroup to deliver
  all proof images as a single photo album (one notification, not five).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 10  # seconds


# ── Internal helpers ──────────────────────────────────────────────────────────

def _api_url(token: str, method: str) -> str:
    return TELEGRAM_API.format(token=token, method=method)


def _post(token: str, method: str, payload: dict[str, Any]) -> bool:
    """POST to Telegram API; returns True on success, logs and returns False on failure."""
    url = _api_url(token, method)
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        data = resp.json()
        if not data.get("ok"):
            logger.error(f"Telegram {method} failed: {data.get('description')}")
            return False
        return True
    except requests.RequestException as exc:
        logger.error(f"Telegram request error ({method}): {exc}")
        return False


def _build_message(donation: dict[str, Any]) -> str:
    """Return a Markdown-formatted alert message for Telegram."""
    method   = donation.get("method", "unknown").upper()
    name     = donation.get("name", "Anonymous")
    email    = donation.get("email", "—")
    amount   = donation.get("amount")
    code     = donation.get("code")
    ref_id   = donation.get("ref_id", "—")
    n_proofs = len(donation.get("proof_urls", []))

    lines = [
        "💝 *New Donation — Hearts for Children*",
        "",
        f"📌 *Ref:* `{ref_id}`",
        f"💳 *Method:* {method}",
        f"👤 *Donor:* {name}",
        f"📧 *Email:* `{email}`",
    ]

    if amount is not None:
        lines.append(f"💰 *Amount:* ${amount}")
    if code:
        lines.append(f"🔑 *Code:* `{code}`")
    if n_proofs:
        lines.append(f"🖼 *Proofs:* {n_proofs} image(s) attached below")

    lines += ["", "⏳ *Status:* Pending verification"]
    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def send_donation_alert(
    bot_token: str,
    chat_id: str,
    donation: dict[str, Any],
) -> bool:
    """
    Send a donation notification to the configured Telegram chat.

    1. Always sends a formatted text message.
    2. If proof URLs exist, follows up with a sendMediaGroup album.

    Returns True if the text message was sent successfully.
    """
    text_payload = {
        "chat_id": chat_id,
        "text": _build_message(donation),
        "parse_mode": "Markdown",
    }
    ok = _post(bot_token, "sendMessage", text_payload)

    # Send proof images as a media group album (single notification)
    proof_urls: list[str] = donation.get("proof_urls", [])
    if proof_urls and ok:
        media = []
        for i, url in enumerate(proof_urls):
            item: dict[str, Any] = {"type": "photo", "media": url}
            # Caption only on the first image to avoid spam
            if i == 0:
                item["caption"] = f"Proof images for ref `{donation.get('ref_id', '')}`"
                item["parse_mode"] = "Markdown"
            media.append(item)

        album_payload = {
            "chat_id": chat_id,
            "media": media,
        }
        _post(bot_token, "sendMediaGroup", album_payload)

    return ok
