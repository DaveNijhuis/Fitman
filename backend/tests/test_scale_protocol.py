"""iCOMON scale protocol: framing, messages and result decoding (#319).

The scale (e.volve, an iCOMON FG2305ULB) speaks a framed protocol on FFB1
(write) and FFB3 (indicate), decoded in #320:

    [seq u16 LE][len u16 LE = 1 + payload][type][payload][check]
    check = sum(type + payload) & 0x1F

scripts/scale_ingest.py sent an `FE ...` command that is not part of it — the
scale ignored every profile it was given — and read the weight from the wrong
bytes. Expected frames come from tests/scale_frames.py, never from the code
under test.
"""

import pytest

from scale import protocol
from tests import scale_frames as F

# ── Framing ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "captured",
    [
        F.HELLO,
        F.ACK_OF_HELLO,
        F.SCALE_ACK,
        F.BD,
        F.GUEST_RECORD,
        F.AD_ALREADY_HAS_IMAGE,
    ],
    ids=["hello", "phone-ack", "scale-ack", "bd", "guest-record", "ad"],
)
def test_check_byte_rule_holds_for_unaltered_captures(captured):
    """The fixtures' seal() uses the same rule, so prove it on real frames first."""
    assert protocol.check(captured[4:-1]) == captured[-1]


def test_parse():
    f = protocol.parse(F.SCALE_ACK)
    assert (f.seq, f.type, f.payload) == (4, 0xA0, bytes.fromhex("0100"))


def test_frame_round_trip():
    f = protocol.parse(F.HELLO)
    assert protocol.frame(f.seq, f.type, f.payload) == F.HELLO


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (F.SCALE_ACK[:-1] + bytes([F.SCALE_ACK[-1] ^ 1]), "check"),
        (F.SCALE_ACK[:2] + b"\x04\x00" + F.SCALE_ACK[4:], "length"),
        (F.SCALE_ACK[:5], "short"),
    ],
    ids=["bad-check", "bad-length", "truncated"],
)
def test_parse_rejects_corrupt_frames(raw, reason):
    with pytest.raises(ValueError, match=reason):
        protocol.parse(raw)


# ── Messages the phone sends ──────────────────────────────────────────────────


def test_sex_age_byte():
    assert protocol.sex_age(male=True, age=40) == 0xA8
    assert protocol.sex_age(male=False, age=31) == 0x1F


@pytest.mark.parametrize("age", [0, 128])
def test_sex_age_rejects_out_of_range(age):
    with pytest.raises(ValueError, match="age"):
        protocol.sex_age(male=True, age=age)


def test_ack():
    assert protocol.ack(0, scale_seq=3) == F.ACK_OF_HELLO


def test_guest_record_sets_the_clock():
    assert (
        protocol.guest_record(
            1, unix_time=F.GUEST_TIME, utc_offset_min=F.UTC_OFFSET_MIN
        )
        == F.GUEST_RECORD
    )


def test_profile():
    frame = protocol.profile(
        2, height_cm=170, last_weight_kg=72.50, male=True, age=40, user_id=F.UID
    )
    assert frame == F.PROFILE


def test_profile_before_any_weigh_in_sends_zero_weight():
    frame = protocol.profile(
        2, height_cm=170, last_weight_kg=None, male=True, age=40, user_id=F.UID
    )
    assert protocol.parse(frame).payload[3:5] == b"\x00\x00"


@pytest.mark.parametrize("height", [49, 256])
def test_profile_rejects_impossible_height(height):
    with pytest.raises(ValueError, match="height"):
        protocol.profile(
            2, height_cm=height, last_weight_kg=None, male=True, age=40, user_id=F.UID
        )


def test_user_id_must_be_four_bytes():
    with pytest.raises(ValueError, match="user id"):
        protocol.profile(
            2, height_cm=170, last_weight_kg=None, male=True, age=40, user_id=b"\x01"
        )


def test_user_record():
    frame = protocol.user_record(
        3,
        unix_time=F.GUEST_TIME,
        utc_offset_min=F.UTC_OFFSET_MIN,
        height_cm=170,
        last_weight_kg=72.50,
        male=True,
        age=40,
        prev_weight_kg=72.40,
        target_weight_kg=70.00,
        user_id=F.UID,
    )
    assert frame == F.USER_RECORD


def test_bd():
    assert protocol.bd(4) == F.BD


def test_name_offer_replay():
    """Fitdays' offer for an existing name image, with the user id substituted."""
    assert protocol.bc(5, user_id=F.UID) == F.NAME_OFFER


# ── Messages the scale sends ──────────────────────────────────────────────────


def test_acked_seq():
    assert protocol.acked_seq(protocol.parse(F.SCALE_ACK)) == 1


def test_acked_seq_rejects_other_messages():
    with pytest.raises(ValueError, match="A0"):
        protocol.acked_seq(protocol.parse(F.HELLO))


def test_result():
    m = protocol.decode_measurement(protocol.parse(F.RESULT))
    assert m.weight_kg == 72.50  # needs the status bit: bytes 11-12 alone are 6.964 kg
    assert m.body_fat_pct == 18.5
    assert m.user_id == F.UID
    assert m.timestamp == F.RESULT_TIME
    assert m.stored is False


def test_result_impedances_in_packet_order():
    """Bytes 16, 18, 20, 22 (20 kHz), then 26, 28, 30, 32 (100 kHz): left arm,
    right arm, right leg, left leg. The arms were the other way round until
    fitting WLA25 to Fitdays showed byte 16 is the left arm (#332)."""
    m = protocol.decode_measurement(protocol.parse(F.RESULT))
    assert (m.la_z20, m.ra_z20, m.rl_z20, m.ll_z20) == (350.0, 340.0, 260.0, 255.0)
    assert (m.la_z100, m.ra_z100, m.rl_z100, m.ll_z100) == (320.0, 310.0, 235.0, 230.0)


def test_trunk_impedance_is_not_exposed():
    """Unresolved (#320): offering it as a settled field would invite use."""
    m = protocol.decode_measurement(protocol.parse(F.RESULT))
    assert not any("trunk" in name for name in vars(m))


def test_stored_measurement_decodes_and_is_marked():
    m = protocol.decode_measurement(protocol.parse(F.STORED))
    assert m.stored is True
    assert m.weight_kg == 72.50
    assert m.user_id == bytes(4)


@pytest.mark.parametrize("frame", [F.SCALE_ACK, F.HELLO], ids=["ack", "hello"])
def test_other_messages_are_not_measurements(frame):
    with pytest.raises(ValueError, match="measurement"):
        protocol.decode_measurement(protocol.parse(frame))


def test_the_old_script_is_gone():
    """Its FE command was never part of the protocol, and its decoder was wrong."""
    from pathlib import Path

    assert not (
        Path(__file__).resolve().parents[2] / "scripts" / "scale_ingest.py"
    ).exists()
