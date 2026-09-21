"""The user's name on the scale's display (#324).

Fitdays sends the name as a 1-bit bitmap: an 18-byte header, then rows of
pixels, offered in a BC message and sent over FFB4 in chunks when the scale
asks. Verified on the real scale (#320, #324): "Dave233" was requested, stored
and displayed.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from scale import name_image, protocol
from scale.handshake import Handshake, ScaleProfile
from tests import scale_frames as F

BACKEND = Path(__file__).resolve().parents[1]


# ── Image format ──────────────────────────────────────────────────────────────


def test_header_reproduces_the_captured_one():
    assert name_image.header(width=184, height=48) == F.NAME_IMAGE_HEADER


@pytest.mark.parametrize(("width", "height"), [(180, 48), (0, 48), (256, 48), (184, 0)])
def test_header_rejects_sizes_the_format_cannot_hold(width, height):
    with pytest.raises(ValueError):
        name_image.header(width=width, height=height)


def test_checksum_is_a_16_bit_byte_sum():
    image = bytes([0xFF] * 300)
    assert name_image.checksum(image) == (0xFF * 300) & 0xFFFF


def test_chunks_carry_an_index_and_148_bytes_each():
    image = bytes(range(256)) * 4 + bytes(100)  # 1124 bytes
    chunks = name_image.chunks(image, chunk_len=149)
    assert [c[0] for c in chunks] == list(range(len(chunks)))
    assert all(len(c) == 149 for c in chunks[:-1])
    assert b"".join(c[1:] for c in chunks) == image


def test_render_has_the_captured_shape():
    image = name_image.render("Alex")
    width, height = image[12], image[14]
    assert image[:12] == F.NAME_IMAGE_HEADER[:12]
    assert height == 48 and width % 8 == 0
    assert len(image) == 18 + width * height // 8


def test_render_draws_ink_with_blank_top_and_bottom_rows():
    image = name_image.render("Alex")
    width = image[12]
    rows = [image[18 + r * width // 8 : 18 + (r + 1) * width // 8] for r in range(48)]
    inked = [i for i, row in enumerate(rows) if any(row)]
    assert inked and inked[0] > 0 and inked[-1] < 47


def test_long_names_are_cut_to_fit():
    image = name_image.render("Bartholomew Montgomery-Fitzgerald")
    assert image[12] <= name_image.MAX_WIDTH


def test_empty_name_is_rejected():
    with pytest.raises(ValueError):
        name_image.render("   ")


def test_image_id_is_stable_per_image_and_never_zero():
    a = name_image.render("Alex")
    assert name_image.image_id(a) == name_image.image_id(name_image.render("Alex"))
    assert name_image.image_id(a) != name_image.image_id(name_image.render("Sam"))
    assert name_image.image_id(bytes(20)) != 0  # 0 means "no image" to the scale


def test_the_font_is_bundled_with_its_licence():
    fonts = BACKEND / "scale" / "fonts"
    assert (fonts / "NotoSans-Bold.ttf").is_file()
    assert "SIL Open Font License" in (fonts / "OFL.txt").read_text()


def test_pillow_is_only_imported_when_a_name_is_rendered():
    """Instances with the scale off never render, so shouldn't load Pillow."""
    code = "import os; os.environ.setdefault('SECRET_KEY','x'); os.environ.setdefault('DATABASE_URL','postgresql://x@localhost/x_test'); import main, sys; print('PIL' in sys.modules)"
    out = subprocess.run(  # noqa: S603 — fixed interpreter and argument
        [sys.executable, "-c", code],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "False", out.stderr


# ── Offer (BC) ────────────────────────────────────────────────────────────────


def test_offer_describes_the_image():
    image = name_image.render("Alex")
    f = protocol.parse(
        protocol.name_offer(5, image=image, user_id=F.UID, image_id=0x1234)
    )
    p = f.payload
    assert f.type == 0xBC
    assert p[:2] == b"\x01\x00"
    assert int.from_bytes(p[2:6], "big") == len(image) == int.from_bytes(p[6:10], "big")
    assert int.from_bytes(p[10:12], "big") == name_image.checksum(image)
    assert p[12:16] == F.UID
    assert p[16:18] == b"\x12\x34"


# ── Handshake ─────────────────────────────────────────────────────────────────

PERSON = ScaleProfile(170, 40, True, None, None, None, F.UID)


def _hs(name: str | None) -> Handshake:
    return Handshake(PERSON, now=lambda: F.GUEST_TIME, utc_offset_min=0, name=name)


def test_with_a_name_the_handshake_offers_our_image():
    hs = _hs("Alex")
    offer = protocol.parse(hs.start()[-1])
    assert offer.type == 0xBC
    assert int.from_bytes(offer.payload[2:6], "big") == len(name_image.render("Alex"))


def test_without_a_name_the_captured_offer_is_replayed():
    """Same offer as before #324; only the sequence number depends on the flow."""
    offer = protocol.parse(_hs(None).start()[-1])
    assert offer.payload == protocol.parse(F.NAME_OFFER).payload


def test_scale_asking_for_the_image_queues_the_chunks_once():
    hs = _hs("Alex")
    hs.start()
    assert hs.on_scale_frame(protocol.parse(F.AD_SEND_IMAGE)) == []
    chunks = hs.take_image_chunks()
    assert b"".join(c[1:] for c in chunks) == name_image.render("Alex")
    assert all(len(c) <= 149 for c in chunks)
    assert hs.take_image_chunks() == []


def test_scale_already_holding_the_image_gets_nothing():
    hs = _hs("Alex")
    hs.start()
    hs.on_scale_frame(protocol.parse(F.AD_ALREADY_HAS_IMAGE))
    assert hs.take_image_chunks() == []
