"""The user's name for the scale's display: a 1-bit bitmap (#324).

Format, from Fitdays' own transfer (#320) and verified on the scale:

    header (18 B): 41 00 41 00 01 00 00 00 0C 00 00 00 [width] [width] [height] 00 00 00
    bitmap:        rows top to bottom, width/8 bytes each, MSB = leftmost pixel, 1 = ink

Offered in BC with a 16-bit byte sum and an image id; sent over FFB4 in
chunks of [index][148 bytes] when the scale asks. Only header byte 13 is
inferred rather than observed varying: it equalled the width in the capture.

The font is Noto Sans Bold (SIL Open Font License 1.1, fonts/OFL.txt).
Pillow is imported only when a name is rendered, so instances that never use
the scale never load it.
"""

from pathlib import Path

HEIGHT = 48
MAX_WIDTH = 248  # the width is one header byte, and a multiple of 8
FONT_SIZE = 32
FONT = Path(__file__).parent / "fonts" / "NotoSans-Bold.ttf"

_HEADER_PREFIX = bytes.fromhex("41 00 41 00 01 00 00 00 0c 00 00 00".replace(" ", ""))


def header(*, width: int, height: int) -> bytes:
    if width % 8 or not 8 <= width <= MAX_WIDTH or not 1 <= height <= 255:
        raise ValueError(f"unsupported name image size {width}x{height}")
    return _HEADER_PREFIX + bytes([width, width, height, 0, 0, 0])


def checksum(image: bytes) -> int:
    """The 16-bit byte sum BC carries for the image."""
    return sum(image) & 0xFFFF


def image_id(image: bytes) -> int:
    """Stable per image, so the scale only asks again when the name changes.

    The scale reports the id it holds (A8) and skips the transfer on a match;
    0 would read as "no image".
    """
    return checksum(image) or 1


def chunks(image: bytes, *, chunk_len: int = 149) -> list[bytes]:
    """FFB4 writes: [index][up to chunk_len - 1 bytes of the image]."""
    step = chunk_len - 1
    return [
        bytes([i]) + image[off : off + step]
        for i, off in enumerate(range(0, len(image), step))
    ]


def render(name: str) -> bytes:
    """Draw `name` in the captured format; names too wide for the display are cut."""
    from PIL import Image, ImageDraw, ImageFont  # only when a name is actually sent

    text = name.strip()
    if not text:
        raise ValueError("name is empty")
    font = ImageFont.truetype(str(FONT), FONT_SIZE)
    while font.getlength(text) > MAX_WIDTH - 4 and len(text) > 1:
        text = text[:-1]
    width = min(MAX_WIDTH, (int(font.getlength(text)) + 4 + 7) // 8 * 8)

    img = Image.new("1", (width, HEIGHT), 0)
    draw = ImageDraw.Draw(img)
    left, top, _right, bottom = draw.textbbox((0, 0), text, font=font)
    # Centred vertically on the glyphs actually drawn, leaving blank margins.
    draw.text((2 - left, (HEIGHT - (bottom - top)) // 2 - top), text, font=font, fill=1)
    # Mode "1" packs rows MSB-first, padded to whole bytes: the scale's layout.
    return header(width=width, height=HEIGHT) + img.tobytes()
