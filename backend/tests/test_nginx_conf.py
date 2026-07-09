"""Static checks that nginx.conf contains required HTTP security headers."""

from pathlib import Path

_CONF = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def _text() -> str:
    return _CONF.read_text()


def test_x_frame_options_header_present():
    assert 'add_header X-Frame-Options "SAMEORIGIN"' in _text()


def test_x_content_type_options_header_present():
    assert 'add_header X-Content-Type-Options "nosniff"' in _text()


def test_referrer_policy_header_present():
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin"' in _text()


def test_content_security_policy_header_present():
    assert "add_header Content-Security-Policy" in _text()


def test_permissions_policy_header_present():
    assert "add_header Permissions-Policy" in _text()
