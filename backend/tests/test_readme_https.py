"""The deploy docs must cover HTTPS via Tailscale (#321).

Web Bluetooth only runs on a secure page, so the smart scale's Weigh-in (#322)
needs Fitman served over HTTPS; Bluefy on iPhone enforces it. `tailscale serve`
does that with a real certificate and no change to Fitman or Docker — verified
on peregrine, and needed again on corvus. Without the steps written down, the
next deploy is back on plain http and the scale silently doesn't work.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "README.md").read_text()


def _deploy_section() -> str:
    start = README.index("## Self-hosting setup")
    end = README.index("\n## ", start + 1)
    return README[start:end]


def test_deploy_docs_enable_tailscale_https_certificates():
    section = _deploy_section()
    assert "HTTPS Certificates" in section
    assert "login.tailscale.com/admin/dns" in section


def test_deploy_docs_serve_fitman_over_https():
    assert "sudo tailscale serve --bg 80" in _deploy_section()


def test_deploy_docs_give_the_https_address():
    assert re.search(r"https://<[^>]+>\.<[^>]+>\.ts\.net", _deploy_section())


def test_deploy_docs_warn_about_the_public_certificate_log():
    """Issuing a certificate publishes the machine and tailnet names."""
    assert "Certificate Transparency" in _deploy_section()


def test_deploy_docs_say_why_https_matters_here():
    section = _deploy_section()
    assert "Web Bluetooth" in section
    assert "SCALE.md" in section


def test_no_plain_http_tailscale_addresses_remain():
    """http://fitman (and fitman.local) predate HTTPS; localhost stays http."""
    for doc in ("README.md", "ARCHITECTURE.md"):
        text = (REPO / doc).read_text()
        assert not re.search(r"http://fitman\b", text), (
            f"{doc} still points at http://fitman"
        )


def test_cors_advice_matches_the_same_origin_setup():
    """nginx proxies /api on the page's own origin, so production needs no CORS entry."""
    env_example = (REPO / ".env.example").read_text()
    assert "set this to your Tailscale hostname" not in env_example
    assert "same origin" in env_example
