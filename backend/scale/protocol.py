"""The iCOMON scale protocol: framing, the messages the phone sends, and results.

The e.volve scale is an iCOMON FG2305ULB. Its protocol was decoded from the
Fitdays app's Bluetooth traffic and verified by replaying it (#320). Frames go
to FFB1 (write with response) and come back on FFB3 (indicate):

    [seq u16 LE][len u16 LE = 1 + payload][type][payload][check]
    check = sum(type + payload) & 0x1F

Phone → scale: B0 ack · BE user record (+clock) · BF profile · BD · BC
Scale → phone: AA hello · A0 ack · A8 · AD · A7 result · A5 stored weigh-in

The scale computes body fat from the BF profile it is sent, so each user's
own height, age and sex go into it. Values marked "replayed" are copied from
the captured traffic without being understood.

No radio code here: scale.handshake decides what to send, and the caller moves
the bytes.
"""

import struct
from dataclasses import dataclass

# Every Fitdays session starts with a BE record for a built-in guest.
_GUEST = {
    "height_cm": 172,
    "weight_kg": 60.00,
    "male": True,
    "age": 24,
    "prev": 50.00,
    "target": 50.00,
}
_BD_PAYLOAD = bytes([0x09])  # replayed
# BC offering the name image Fitdays sent (replayed; #324 renders our own).
_BC_HEAD = bytes.fromhex("01 00 00 00 04 62 00 00 04 62 ed de".replace(" ", ""))
_BC_TAIL = bytes.fromhex("1915")

RESULT = 0xA7
STORED = 0xA5
_MEASUREMENT_LEN = 37  # payload bytes of an A7/A5 frame (43-byte frame)


@dataclass(frozen=True)
class Frame:
    seq: int
    type: int
    payload: bytes


@dataclass(frozen=True)
class Measurement:
    """One weigh-in from an A7 result or an A5 stored record.

    Impedances are in packet order under the model's column names. Which limb
    each position is, and the trunk bytes, are not settled (#320, #325), so
    trunk is deliberately absent.
    """

    timestamp: int  # the scale's clock, Unix seconds (set by the BE record)
    weight_kg: float
    body_fat_pct: float  # computed by the scale from the BF profile
    user_id: bytes
    stored: bool  # True for A5: taken while nothing was connected
    ra_z20: float
    la_z20: float
    rl_z20: float
    ll_z20: float
    ra_z100: float
    la_z100: float
    rl_z100: float
    ll_z100: float


def check(type_and_payload: bytes) -> int:
    return sum(type_and_payload) & 0x1F


def frame(seq: int, type_: int, payload: bytes) -> bytes:
    body = bytes([type_]) + payload
    return struct.pack("<HH", seq & 0xFFFF, len(body)) + body + bytes([check(body)])


def parse(data: bytes) -> Frame:
    if len(data) < 6:
        raise ValueError(f"frame too short: {len(data)} bytes")
    seq, length = struct.unpack_from("<HH", data, 0)
    if length != len(data) - 5:
        raise ValueError(
            f"length field {length} disagrees with a {len(data)}-byte frame"
        )
    body = data[4:-1]
    if check(body) != data[-1]:
        raise ValueError(f"check byte {data[-1]:#04x}, expected {check(body):#04x}")
    return Frame(seq, body[0], bytes(body[1:]))


def sex_age(*, male: bool, age: int) -> int:
    if not 1 <= age <= 127:
        raise ValueError(f"age {age} out of range 1-127")
    return (0x80 if male else 0) | age


def _kg(value: float | None) -> bytes:
    return struct.pack(">H", round((value or 0) * 100))


def _uid(user_id: bytes) -> bytes:
    if len(user_id) != 4:
        raise ValueError(f"user id must be 4 bytes, got {len(user_id)}")
    return user_id


def _height(height_cm: int) -> int:
    if not 50 <= height_cm <= 255:
        raise ValueError(f"height {height_cm} cm out of range 50-255")
    return height_cm


def ack(seq: int, scale_seq: int) -> bytes:
    """B0: acknowledge a scale message (hello, result, stored record) by its seq."""
    return frame(seq, 0xB0, struct.pack("<H", scale_seq))


def profile(
    seq: int,
    *,
    height_cm: int,
    last_weight_kg: float | None,
    male: bool,
    age: int,
    user_id: bytes,
) -> bytes:
    """BF: the profile the scale computes body fat from."""
    payload = (
        bytes([0x01, 0x01, _height(height_cm)])
        + _kg(last_weight_kg)
        + bytes([sex_age(male=male, age=age)])
        + bytes(4)  # zero in every BF seen
        + bytes([0x0F])
        + _uid(user_id)
        + bytes([0x01, 0x01])
    )
    return frame(seq, 0xBF, payload)


def _record(
    seq: int,
    *,
    unix_time: int,
    utc_offset_min: int,
    height_cm: int,
    weight_kg: float | None,
    male: bool,
    age: int,
    prev_kg: float | None,
    target_kg: float | None,
    flag: int,
    user_id: bytes,
    tail: bytes,
) -> bytes:
    payload = (
        struct.pack(">Ih", unix_time, utc_offset_min)
        + bytes([0x01, _height(height_cm)])
        + _kg(weight_kg)
        + bytes([sex_age(male=male, age=age)])
        + _kg(prev_kg)
        + _kg(target_kg)
        + bytes([flag])
        + user_id
        + tail
    )
    return frame(seq, 0xBE, payload)


def guest_record(seq: int, *, unix_time: int, utc_offset_min: int) -> bytes:
    """BE for the built-in guest; also sets the scale's clock."""
    g = _GUEST
    return _record(
        seq,
        unix_time=unix_time,
        utc_offset_min=utc_offset_min,
        height_cm=int(g["height_cm"]),
        weight_kg=float(g["weight_kg"]),
        male=bool(g["male"]),
        age=int(g["age"]),
        prev_kg=float(g["prev"]),
        target_kg=float(g["target"]),
        flag=0x2F,
        user_id=bytes(4),
        tail=bytes(2),
    )


def user_record(
    seq: int,
    *,
    unix_time: int,
    utc_offset_min: int,
    height_cm: int,
    last_weight_kg: float | None,
    male: bool,
    age: int,
    prev_weight_kg: float | None,
    target_weight_kg: float | None,
    user_id: bytes,
) -> bytes:
    """BE for a real user; also sets the scale's clock."""
    return _record(
        seq,
        unix_time=unix_time,
        utc_offset_min=utc_offset_min,
        height_cm=height_cm,
        weight_kg=last_weight_kg,
        male=male,
        age=age,
        prev_kg=prev_weight_kg,
        target_kg=target_weight_kg,
        flag=0x0F,
        user_id=_uid(user_id),
        tail=bytes([0x01, 0x01]),
    )


def bd(seq: int) -> bytes:
    """BD 09 (replayed). The scale answers A8 with the user's stored name image id."""
    return frame(seq, 0xBD, _BD_PAYLOAD)


def bc(seq: int, *, user_id: bytes) -> bytes:
    """BC (replayed with our user id). The scale answers AD."""
    return frame(seq, 0xBC, _BC_HEAD + _uid(user_id) + _BC_TAIL)


def acked_seq(f: Frame) -> int:
    """A0: the sequence number of the phone frame being acknowledged."""
    if f.type != 0xA0 or len(f.payload) < 2:
        raise ValueError("not an A0 acknowledgement")
    return int(struct.unpack_from("<H", f.payload, 0)[0])


def _ohm(p: bytes, i: int) -> float:
    return int.from_bytes(p[i : i + 2], "little") / 10


def decode_measurement(f: Frame) -> Measurement:
    """A7 result or A5 stored record. Offsets below are into the payload (byte 5 on)."""
    if f.type not in (RESULT, STORED) or len(f.payload) != _MEASUREMENT_LEN:
        raise ValueError(
            f"not a measurement frame (type {f.type:#04x}, {len(f.payload)} bytes)"
        )
    p = f.payload
    return Measurement(
        timestamp=int(struct.unpack_from(">I", p, 0)[0]),
        # Bit 0 of the status byte is weight bit 16: weights ≥ 65.536 kg need it.
        weight_kg=(((p[5] & 1) << 16) | (p[6] << 8) | p[7]) / 1000,
        body_fat_pct=int(struct.unpack_from(">H", p, 35)[0]) / 10,
        user_id=bytes(p[30:34]),
        stored=f.type == STORED,
        ra_z20=_ohm(p, 11),
        la_z20=_ohm(p, 13),
        rl_z20=_ohm(p, 15),
        ll_z20=_ohm(p, 17),
        ra_z100=_ohm(p, 21),
        la_z100=_ohm(p, 23),
        rl_z100=_ohm(p, 25),
        ll_z100=_ohm(p, 27),
    )


def name_offer(seq: int, *, image: bytes, user_id: bytes, image_id: int) -> bytes:
    """BC offering a name image (#324): 01 00, size u32 BE twice, byte sum u16 BE,
    user id, image id. The scale answers AD 01 00 .. [chunk len] to ask for it,
    or AD 01 04 .. when it already holds that image id for the user."""
    size = len(image).to_bytes(4, "big")
    payload = (
        bytes([0x01, 0x00])
        + size
        + size
        + (sum(image) & 0xFFFF).to_bytes(2, "big")
        + _uid(user_id)
        + (image_id & 0xFFFF).to_bytes(2, "big")
    )
    return frame(seq, 0xBC, payload)
