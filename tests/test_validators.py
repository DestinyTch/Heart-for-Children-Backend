"""
tests/test_validators.py
=========================
Unit tests for pure validation logic — no Flask context needed.
"""

import io
import pytest
from unittest.mock import MagicMock

from services.validators import (
    ValidationError,
    validate_email,
    validate_images,
    validate_method,
)


# ── email ─────────────────────────────────────────────────────────────────────

class TestValidateEmail:
    def test_valid_email(self):
        assert validate_email("donor@example.com") == "donor@example.com"

    def test_strips_whitespace(self):
        assert validate_email("  DONOR@EXAMPLE.COM  ") == "donor@example.com"

    def test_missing_at(self):
        with pytest.raises(ValidationError, match="Invalid email"):
            validate_email("notanemail.com")

    def test_empty_string(self):
        with pytest.raises(ValidationError, match="required"):
            validate_email("")

    def test_none(self):
        with pytest.raises(ValidationError, match="required"):
            validate_email(None)


# ── method ────────────────────────────────────────────────────────────────────

class TestValidateMethod:
    @pytest.mark.parametrize("method", ["btc", "sol", "usdt", "amazon", "apple", "steam", "sephora", "razer"])
    def test_valid_methods(self, method):
        assert validate_method(method) == method

    def test_uppercase_normalised(self):
        assert validate_method("BTC") == "btc"

    def test_invalid_method(self):
        with pytest.raises(ValidationError, match="must be one of"):
            validate_method("paypal")

    def test_none(self):
        with pytest.raises(ValidationError):
            validate_method(None)


# ── images ────────────────────────────────────────────────────────────────────

def _make_file(mimetype="image/jpeg", size_bytes=1024):
    """Helper: create a fake Werkzeug FileStorage-like mock."""
    f = MagicMock()
    f.filename = "proof.jpg"
    f.mimetype = mimetype
    buf = io.BytesIO(b"x" * size_bytes)
    f.stream = buf
    return f


class TestValidateImages:
    def test_empty_list_ok(self):
        assert validate_images([]) == []

    def test_valid_single_image(self):
        files = [_make_file()]
        assert len(validate_images(files)) == 1

    def test_too_many_images(self):
        files = [_make_file() for _ in range(6)]
        with pytest.raises(ValidationError, match="Maximum 5"):
            validate_images(files)

    def test_invalid_mimetype(self):
        f = _make_file(mimetype="application/pdf")
        with pytest.raises(ValidationError, match="unsupported type"):
            validate_images([f])

    def test_oversized_image(self):
        f = _make_file(size_bytes=6 * 1024 * 1024)  # 6 MB
        with pytest.raises(ValidationError, match="MB"):
            validate_images([f])

    def test_webp_accepted(self):
        files = [_make_file(mimetype="image/webp")]
        assert len(validate_images(files)) == 1
