"""Scale frames for the protocol tests (#319).

Captured from the Fitdays app talking to the scale (iCOMON FG2305ULB) on
2026-09-21 — see #320 for how. Frames that carry no personal data are used
exactly as captured. Frames that did (height, age, weights, impedances, body
fat, user id) keep the captured structure and constant bytes, but their body
values are replaced with a made-up person, and their check byte recomputed:
this repository is public. The byte-for-byte comparison against the unaltered
captures lives with the research notes, not here.

The made-up person: male, 40, 170 cm, last weight 72.50 kg, previous weight
72.40 kg, target 70.00 kg, scale user id 0a 0b 0c 0d.
"""


def seal(hex_without_check: str) -> bytes:
    """Append the check byte: sum(type + payload) & 0x1F (bytes 4 onward)."""
    raw = bytes.fromhex(hex_without_check.replace(" ", ""))
    return raw + bytes([sum(raw[4:]) & 0x1F])


def unhex(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


# ── As captured (no personal data) ────────────────────────────────────────────

HELLO = unhex(
    "0a 00 1e 00 aa 93 79 1e 08 52 25 01 0a 00 00 00 00 00 00 00 00 00 00 00 00 00 01 a0 01 01 00 00 ff ff 1f"
)
ACK_OF_HELLO = unhex("00 00 03 00 b0 03 00 13")  # phone acknowledging scale seq 3
SCALE_ACK = unhex("04 00 03 00 a0 01 00 01")  # scale acknowledging phone seq 1
BD = unhex("04 00 02 00 bd 09 06")
GUEST_RECORD = unhex(  # BE for the built-in guest; also sets the clock
    "01 00 17 00 be 6a b1 1e 59 00 78 01 ac 17 70 98 13 88 13 88 2f 00 00 00 00 00 00 19"
)
GUEST_TIME = 0x6AB11E59
UTC_OFFSET_MIN = 120
AD_ALREADY_HAS_IMAGE = unhex("0f 00 06 00 ad 01 04 00 00 00 12")
AD_SEND_IMAGE = unhex("63 00 06 00 ad 01 00 20 00 95 03")  # 0x95 = 149-byte chunks
# The 18-byte header of Fitdays' name image (184 x 48 px). The bitmap that
# followed spelled a real name, so it stays out of this public repository.
NAME_IMAGE_HEADER = unhex("41 00 41 00 01 00 00 00 0c 00 00 00 b8 b8 30 00 00 00")

# ── Captured structure, made-up person ────────────────────────────────────────

UID = unhex("0a 0b 0c 0d")

PROFILE = seal("02 00 12 00 bf 01 01 aa 1c 52 a8 00 00 00 00 0f 0a 0b 0c 0d 01 01")
USER_RECORD = seal(
    "03 00 17 00 be 6a b1 1e 59 00 78 01 aa 1c 52 a8 1c 48 1b 58 0f 0a 0b 0c 0d 01 01"
)
NAME_OFFER = seal(
    "05 00 13 00 bc 01 00 00 00 04 62 00 00 04 62 ed de 0a 0b 0c 0d 19 15"
)

# A7 result: 72.50 kg (status bit 0 carries 65536 g), impedances in packet
# order, body fat 18.5 %, computed for UID.
RESULT = seal(
    "11 00 26 00 a7"
    " 6a b1 1e b6"  # 5-8   timestamp
    " 25 61"  # 9-10  ?, status (bit 0 = weight bit 16)
    " 1b 34"  # 11-12 weight low 16 bits
    " 00 0a 01"  # 13-15
    " ac 0d 48 0d 28 0a f6 09"  # 16-23 20 kHz: 350.0 340.0 260.0 255.0
    " 1e 00"  # 24-25 trunk? (unresolved, #320)
    " 80 0c 1c 0c 2e 09 fc 08"  # 26-33 100 kHz: 320.0 310.0 235.0 230.0
    " 14"  # 34    trunk? (unresolved)
    " 0a 0b 0c 0d"  # 35-38 user id
    " 01"  # 39
    " 00 b9"  # 40-41 body fat 18.5 %
)
RESULT_TIME = 0x6AB11EB6

# A5: a weigh-in stored while nothing was connected. Same layout, no user id.
STORED = seal(
    "5e 00 26 00 a5 6a b1 24 0a 25 61 1b 34 00 0a 01"
    " ac 0d 48 0d 28 0a f6 09 1e 00 80 0c 1c 0c 2e 09 fc 08 14"
    " 00 00 00 00 01 01 b9"
)
