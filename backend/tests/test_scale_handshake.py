"""Scale handshake: what to send back for each scale message (#319).

The order is Fitdays': hello → ack, guest record (sets the clock), profile,
user record, BD, name offer; after the weigh-in, the result → ack. The scale
computes body fat from the profile it is sent.
"""

from scale import protocol
from scale.handshake import Handshake, ScaleProfile
from tests import scale_frames as F

PERSON = ScaleProfile(
    height_cm=170,
    age=40,
    male=True,
    last_weight_kg=72.50,
    prev_weight_kg=72.40,
    target_weight_kg=70.00,
    user_id=F.UID,
)


def _hs() -> Handshake:
    return Handshake(PERSON, now=lambda: F.GUEST_TIME, utc_offset_min=F.UTC_OFFSET_MIN)


def _types(frames: list[bytes]) -> list[int]:
    return [protocol.parse(f).type for f in frames]


def test_hello_is_answered_with_the_fitdays_sequence():
    out = _hs().on_scale_frame(protocol.parse(F.HELLO))
    assert _types(out) == [0xB0, 0xBE, 0xBF, 0xBE, 0xBD, 0xBC]
    assert protocol.parse(out[0]).payload == b"\x0a\x00"  # acknowledges the hello's seq
    assert [protocol.parse(f).seq for f in out] == [0, 1, 2, 3, 4, 5]


def test_sequence_carries_the_profile():
    out = _hs().on_scale_frame(protocol.parse(F.HELLO))
    assert out[1] == F.GUEST_RECORD
    assert out[2] == F.PROFILE
    assert out[3] == F.USER_RECORD
    assert out[4] == F.BD
    assert out[5] == F.NAME_OFFER


def test_sequence_is_sent_once():
    hs = _hs()
    hs.on_scale_frame(protocol.parse(F.HELLO))
    assert _types(hs.on_scale_frame(protocol.parse(F.HELLO))) == [0xB0]


def test_start_without_a_hello():
    """If the hello went out before the phone subscribed, start unprompted."""
    hs = _hs()
    assert _types(hs.start()) == [0xBE, 0xBF, 0xBE, 0xBD, 0xBC]
    assert hs.start() == []


def test_result_is_acknowledged_and_kept():
    hs = _hs()
    hs.start()
    out = hs.on_scale_frame(protocol.parse(F.RESULT))
    assert out == [protocol.ack(5, 0x11)]
    assert hs.result is not None and hs.result.body_fat_pct == 18.5


def test_stored_measurement_is_acknowledged_but_is_not_the_result():
    """A5 is re-offered every ~10 s until acknowledged."""
    hs = _hs()
    hs.start()
    out = hs.on_scale_frame(protocol.parse(F.STORED))
    assert _types(out) == [0xB0]
    assert hs.result is None
    assert [m.weight_kg for m in hs.stored] == [72.50]


def test_a_stored_measurement_offered_twice_is_kept_once():
    hs = _hs()
    hs.start()
    hs.on_scale_frame(protocol.parse(F.STORED))
    again = protocol.parse(F.STORED)
    hs.on_scale_frame(protocol.Frame(again.seq + 6, again.type, again.payload))
    assert len(hs.stored) == 1


def test_acknowledgements_need_no_reply():
    hs = _hs()
    hs.start()
    assert hs.on_scale_frame(protocol.parse(F.SCALE_ACK)) == []
    assert hs.on_scale_frame(protocol.parse(F.AD_ALREADY_HAS_IMAGE)) == []


def test_default_offset_is_the_local_timezone():
    import time

    hs = Handshake(PERSON)
    assert hs.utc_offset_min == round(time.localtime().tm_gmtoff / 60)
