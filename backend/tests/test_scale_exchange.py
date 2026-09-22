"""POST /api/scale/exchange: the backend's side of a weigh-in (#323).

The phone relays frames between the scale and this endpoint over Web
Bluetooth (#322): what the scale sent goes in, what to write to FFB1 comes
back. The backend builds the handshake from the logged-in user's own profile —
the scale computes body fat from it — and stores the result for that user.

The handshake's small state (next phone sequence number, whether the profile
went out) travels with the phone, so the backend stays stateless between
requests. Frames come from tests/scale_frames.py.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import SessionLocal
from models.measurement import BodyMeasurement
from models.user import User
from scale import protocol
from tests import scale_frames as F

URL = "/api/scale/exchange"


@pytest.fixture
def scale_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "scale_enabled", True)
    yield


def _login(client: TestClient, username: str, password: str) -> dict:
    token = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _new_user(client: TestClient, **profile: object) -> tuple[dict, str]:
    """A fresh user with the given profile; returns (auth headers, username)."""
    admin = _login(client, "testuser", "testpass")
    username = f"scale_{uuid4().hex[:10]}"
    resp = client.post(
        "/api/admin/users",
        json={"username": username, "password": "pass1234"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    headers = _login(client, username, "pass1234")
    if profile:
        assert (
            client.patch("/api/profile", json=profile, headers=headers).status_code
            == 200
        )
    return headers, username


COMPLETE = {"height_cm": 170, "birth_year": 1990, "sex": "male"}


@pytest.fixture
def person(client: TestClient) -> tuple[dict, str]:
    return _new_user(client, **COMPLETE)


def _exchange(client: TestClient, headers: dict, frames: list[bytes], **state: object):
    body = {"frames": [f.hex() for f in frames], "utc_offset_min": 120, **state}
    return client.post(URL, json=body, headers=headers)


def _scale_uid(username: str) -> str | None:
    with SessionLocal() as db:
        return db.query(User).filter(User.username == username).one().scale_user_id


def _measurements(username: str) -> list[BodyMeasurement]:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        return (
            db.query(BodyMeasurement).filter(BodyMeasurement.user_id == user.id).all()
        )


def _result_for(uid: bytes, template: bytes = F.RESULT) -> bytes:
    """The fixture result, re-addressed to another scale user id."""
    body = template[:35] + uid + template[39:-1]
    return body + bytes([protocol.check(body[4:])])


def _types(send: list[str]) -> list[int]:
    return [protocol.parse(bytes.fromhex(h)).type for h in send]


# ── Opt-in and auth ───────────────────────────────────────────────────────────


def test_endpoint_does_not_exist_while_the_scale_is_off(
    client: TestClient, person, monkeypatch: pytest.MonkeyPatch
):
    # Explicitly off: a developer's .env may have SCALE_ENABLED=true.
    monkeypatch.setattr(settings, "scale_enabled", False)
    assert _exchange(client, person[0], [F.HELLO]).status_code == 404


def test_requires_auth(client: TestClient, scale_on):
    from main import app

    assert TestClient(app).post(URL, json={"frames": []}).status_code == 401


# ── Scale user id ─────────────────────────────────────────────────────────────


def test_first_exchange_creates_a_scale_user_id_and_later_ones_reuse_it(
    client: TestClient, scale_on, person
):
    headers, username = person
    assert _scale_uid(username) is None
    _exchange(client, headers, [F.HELLO])
    uid = _scale_uid(username)
    assert uid is not None and len(uid) == 8 and uid != "00000000"
    _exchange(client, headers, [F.HELLO])
    assert _scale_uid(username) == uid


def test_scale_user_ids_differ_between_users(client: TestClient, scale_on):
    a, b = _new_user(client, **COMPLETE), _new_user(client, **COMPLETE)
    _exchange(client, a[0], [F.HELLO])
    _exchange(client, b[0], [F.HELLO])
    assert _scale_uid(a[1]) != _scale_uid(b[1])


# ── The handshake ─────────────────────────────────────────────────────────────


def test_hello_is_answered_with_the_handshake_built_from_the_users_profile(
    client: TestClient, scale_on, person
):
    headers, username = person
    resp = _exchange(client, headers, [F.HELLO])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert _types(body["send"]) == [0xB0, 0xBE, 0xBF, 0xBE, 0xBD, 0xBC]
    bf = protocol.parse(bytes.fromhex(body["send"][2])).payload
    age = datetime.now(timezone.utc).year - 1990
    assert bf[2] == 170  # height
    assert bf[5] == protocol.sex_age(male=True, age=age)
    assert bf[3:5] == b"\x00\x00"  # no earlier weigh-in
    assert bf[11:15].hex() == _scale_uid(username)  # after the 0F byte
    assert (body["phone_seq"], body["sequence_sent"]) == (6, True)


def test_clock_is_sent_with_the_phones_utc_offset(client: TestClient, scale_on, person):
    """The container runs in UTC; the phone knows the user's timezone."""
    body = _exchange(client, person[0], [F.HELLO]).json()
    guest = protocol.parse(bytes.fromhex(body["send"][1])).payload
    assert int.from_bytes(guest[4:6], "big", signed=True) == 120


def test_no_frames_starts_the_handshake_unprompted(
    client: TestClient, scale_on, person
):
    """For when the scale's hello arrived before the phone subscribed."""
    body = _exchange(client, person[0], []).json()
    assert _types(body["send"]) == [0xBE, 0xBF, 0xBE, 0xBD, 0xBC]


def test_state_carries_between_requests(client: TestClient, scale_on, person):
    first = _exchange(client, person[0], [F.HELLO]).json()
    again = _exchange(
        client,
        person[0],
        [F.HELLO],
        phone_seq=first["phone_seq"],
        sequence_sent=first["sequence_sent"],
    ).json()
    assert _types(again["send"]) == [0xB0]
    assert protocol.parse(bytes.fromhex(again["send"][0])).seq == 6


def test_acknowledgements_need_no_reply(client: TestClient, scale_on, person):
    body = _exchange(
        client, person[0], [F.SCALE_ACK], phone_seq=2, sequence_sent=True
    ).json()
    assert body["send"] == []


# ── Results ───────────────────────────────────────────────────────────────────


def _handshaken(client: TestClient, headers: dict, username: str) -> tuple[dict, bytes]:
    state = _exchange(client, headers, [F.HELLO]).json()
    return state, bytes.fromhex(_scale_uid(username) or "")


def test_result_for_this_user_is_stored_once(client: TestClient, scale_on, person):
    headers, username = person
    state, uid = _handshaken(client, headers, username)
    resp = _exchange(
        client,
        headers,
        [_result_for(uid)],
        phone_seq=state["phone_seq"],
        sequence_sent=True,
    ).json()
    assert _types(resp["send"]) == [0xB0]  # acknowledged, or the scale re-sends it
    assert resp["measurement"]["weight_kg"] == 72.5
    assert resp["measurement"]["body_fat_pct"] == 18.5
    assert resp["error"] is None
    [m] = _measurements(username)
    assert (
        m.weight_kg,
        m.body_fat_pct,
        m.la_z20,
        m.ll_z100,
    ) == (  # byte 16: left arm (#332)
        72.5,
        18.5,
        350.0,
        230.0,
    )
    assert m.height_cm == 170


def test_result_for_another_scale_user_is_acknowledged_but_not_stored(
    client: TestClient, scale_on, person
):
    headers, username = person
    state, uid = _handshaken(client, headers, username)
    other = bytes([uid[0] ^ 0xFF]) + uid[1:]
    resp = _exchange(
        client,
        headers,
        [_result_for(other)],
        phone_seq=state["phone_seq"],
        sequence_sent=True,
    ).json()
    assert _types(resp["send"]) == [0xB0]
    assert resp["measurement"] is None
    assert "different" in resp["error"]
    assert _measurements(username) == []


def test_stored_weigh_ins_are_acknowledged_but_not_stored(
    client: TestClient, scale_on, person
):
    """A5 carries no user id: there's no telling whose it is."""
    headers, username = person
    state, _ = _handshaken(client, headers, username)
    resp = _exchange(
        client, headers, [F.STORED], phone_seq=state["phone_seq"], sequence_sent=True
    ).json()
    assert _types(resp["send"]) == [0xB0]
    assert resp["measurement"] is None
    assert _measurements(username) == []


def test_the_next_handshake_carries_the_last_weight(
    client: TestClient, scale_on, person
):
    headers, username = person
    state, uid = _handshaken(client, headers, username)
    _exchange(
        client,
        headers,
        [_result_for(uid)],
        phone_seq=state["phone_seq"],
        sequence_sent=True,
    )
    bf = protocol.parse(
        bytes.fromhex(_exchange(client, headers, [F.HELLO]).json()["send"][2])
    )
    assert bf.payload[3:5] == (7250).to_bytes(2, "big")  # 72.50 kg


# ── Refusals ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("profile", "missing"),
    [
        ({"birth_year": 1990, "sex": "male"}, "height"),
        ({"height_cm": 170, "sex": "male"}, "birth year"),
        ({"height_cm": 170, "birth_year": 1990}, "sex"),
        ({"height_cm": 170, "birth_year": 1990, "sex": "other"}, "sex"),
    ],
    ids=["no-height", "no-birth-year", "no-sex", "sex-other"],
)
def test_incomplete_profile_is_refused_by_name(
    client: TestClient, scale_on, profile, missing
):
    """No fallback values: the scale would compute body fat from them."""
    headers, username = _new_user(client, **profile)
    resp = _exchange(client, headers, [F.HELLO])
    assert resp.status_code == 422
    assert missing in resp.json()["detail"]
    assert _scale_uid(username) is None


@pytest.mark.parametrize(
    "frames",
    [["zz"], [F.SCALE_ACK[:-1].hex() + "00"], ["00" * 300]],
    ids=["not-hex", "bad-check-byte", "oversized"],
)
def test_corrupt_frames_are_refused(client: TestClient, scale_on, person, frames):
    resp = client.post(URL, json={"frames": frames}, headers=person[0])
    assert resp.status_code == 422


def test_a_generated_id_of_all_zeros_or_already_taken_is_skipped(
    client: TestClient, scale_on, monkeypatch: pytest.MonkeyPatch
):
    """00000000 is the scale's "no user"; a collision would merge two histories."""
    first, _ = _new_user(client, **COMPLETE)
    _exchange(client, first, [F.HELLO])
    taken = bytes.fromhex(_scale_uid(_new_user_name(first, client)) or "")
    draws = iter([bytes(4), taken, bytes.fromhex("0badf00d")])
    monkeypatch.setattr("routers.scale.secrets.token_bytes", lambda n: next(draws))
    headers, username = _new_user(client, **COMPLETE)
    _exchange(client, headers, [F.HELLO])
    assert _scale_uid(username) == "0badf00d"


def _new_user_name(headers: dict, client: TestClient) -> str:
    return client.get("/api/profile", headers=headers).json()["username"]


def test_a_height_the_scale_cannot_represent_is_refused(client: TestClient, scale_on):
    headers, _ = _new_user(client, height_cm=300, birth_year=1990, sex="male")
    resp = _exchange(client, headers, [F.HELLO])
    assert resp.status_code == 422
    assert "height" in resp.json()["detail"]


# ── Name on the display (#324) ────────────────────────────────────────────────


def test_the_offer_names_the_user_with_a_stable_image_id(
    client: TestClient, scale_on, person
):
    headers, _ = person
    first = protocol.parse(
        bytes.fromhex(_exchange(client, headers, [F.HELLO]).json()["send"][-1])
    )
    again = protocol.parse(
        bytes.fromhex(_exchange(client, headers, [F.HELLO]).json()["send"][-1])
    )
    assert first.type == 0xBC
    assert (
        first.payload[16:18] == again.payload[16:18]
    )  # unchanged name: the scale won't ask again


def test_a_new_display_name_changes_the_image_id(client: TestClient, scale_on, person):
    headers, _ = person
    before = protocol.parse(
        bytes.fromhex(_exchange(client, headers, [F.HELLO]).json()["send"][-1])
    )
    client.patch("/api/profile", json={"display_name": "Someone Else"}, headers=headers)
    after = protocol.parse(
        bytes.fromhex(_exchange(client, headers, [F.HELLO]).json()["send"][-1])
    )
    assert before.payload[16:18] != after.payload[16:18]


def test_when_the_scale_asks_the_image_chunks_are_returned(
    client: TestClient, scale_on, person
):
    headers, username = person
    state = _exchange(client, headers, [F.HELLO]).json()
    resp = _exchange(
        client,
        headers,
        [F.AD_SEND_IMAGE],
        phone_seq=state["phone_seq"],
        sequence_sent=True,
    ).json()
    chunks = [bytes.fromhex(c) for c in resp["image_chunks"]]
    assert chunks, "no image chunks returned"
    assert [c[0] for c in chunks] == list(range(len(chunks)))
    image = b"".join(c[1:] for c in chunks)
    assert image[14] == 48  # a 48-px-high name image
    assert resp["send"] == []


def test_no_chunks_when_the_scale_already_has_the_image(
    client: TestClient, scale_on, person
):
    headers, _ = person
    state = _exchange(client, headers, [F.HELLO]).json()
    resp = _exchange(
        client,
        headers,
        [F.AD_ALREADY_HAS_IMAGE],
        phone_seq=state["phone_seq"],
        sequence_sent=True,
    ).json()
    assert resp["image_chunks"] == []
