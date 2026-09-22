"""Filling in derived fields for measurements stored without them (#325).

Scale weigh-ins made before #325 have every raw input — weight, the scale's
body fat, impedances — but no derived fields, because the formulas refused to
run without trunk impedance. The backfill runs at startup, fills only rows
whose derived fields are empty, and never overwrites a value.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from measurement_backfill import backfill_derived
from models.measurement import BodyMeasurement
from models.user import User

RAW = dict(  # a made-up person: this repo is public
    weight_kg=72.5,
    body_fat_pct=18.5,
    height_cm=170.0,
    la_z20=350.0,
    ra_z20=340.0,
    rl_z20=260.0,
    ll_z20=255.0,
    la_z100=320.0,
    ra_z100=310.0,
    rl_z100=235.0,
    ll_z100=230.0,
)


@pytest.fixture
def user(database: None) -> int:
    with SessionLocal() as db:
        u = User(
            username=f"backfill_{uuid4().hex[:10]}",
            hashed_password="x",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
            birth_year=1986,
            sex="male",
            height_cm=170.0,
        )
        db.add(u)
        db.commit()
        return u.id


def _add(user_id: int, **fields: object) -> int:
    with SessionLocal() as db:
        m = BodyMeasurement(
            user_id=user_id,
            recorded_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
            **fields,
        )
        db.add(m)
        db.commit()
        return m.id


def _get(measurement_id: int) -> BodyMeasurement:
    with SessionLocal() as db:
        return db.get(BodyMeasurement, measurement_id)  # type: ignore[return-value]


def test_a_scale_weigh_in_without_derived_fields_gets_them(user):
    mid = _add(user, **RAW)
    with SessionLocal() as db:
        assert backfill_derived(db) >= 1
    m = _get(mid)
    assert m.bmi == pytest.approx(72.5 / 1.70**2, abs=0.01)
    assert m.fat_mass_kg is not None and m.visceral_fat_grade is not None
    assert m.weight_kg == 72.5 and m.body_fat_pct == 18.5  # raw inputs untouched


def test_age_is_taken_at_the_time_of_the_measurement(user):
    """Born 1986, measured 2026: 40 — whatever year the backfill runs in."""
    mid = _add(user, **RAW)
    with SessionLocal() as db:
        backfill_derived(db)
    m = _get(mid)
    assert m.body_age is not None
    from formulas import ImpedanceInputs, UserProfile, calculate_all

    expected = calculate_all(
        UserProfile(age=40, height_cm=170.0, sex=1, weight_kg=72.5),
        ImpedanceInputs(
            **{k: v for k, v in RAW.items() if k.endswith(("z20", "z100"))},
            trunk_z20=None,
            trunk_z100=None,
            body_fat_pct=18.5,
        ),
    )
    assert m.body_age == expected["body_age"]


def test_measurements_that_already_have_derived_fields_are_left_alone(user):
    mid = _add(user, **RAW, bmi=12.34)
    with SessionLocal() as db:
        backfill_derived(db)
    m = _get(mid)
    assert m.bmi == 12.34
    assert m.visceral_fat_grade is None  # not "completed" either


def test_measurements_without_body_fat_are_skipped(user):
    mid = _add(user, weight_kg=80.0)
    with SessionLocal() as db:
        backfill_derived(db)
    assert _get(mid).bmi is None


def test_running_it_twice_changes_nothing_the_second_time(user):
    _add(user, **RAW)
    with SessionLocal() as db:
        backfill_derived(db)
    with SessionLocal() as db:
        assert backfill_derived(db) == 0


def test_it_runs_at_startup(monkeypatch: pytest.MonkeyPatch, database: None):
    import main

    calls: list[object] = []

    def spy(db: object) -> int:
        calls.append(db)
        return 0

    monkeypatch.setattr(main, "backfill_derived", spy)
    with TestClient(main.app):
        pass
    assert len(calls) == 1


def test_height_comes_from_the_profile_when_the_measurement_has_none(user):
    raw = {k: v for k, v in RAW.items() if k != "height_cm"}
    mid = _add(user, **raw)
    with SessionLocal() as db:
        backfill_derived(db)
    m = _get(mid)
    assert m.height_cm == 170.0
    assert m.bmi == pytest.approx(72.5 / 1.70**2, abs=0.01)


def _user_without_birth_year() -> int:
    with SessionLocal() as db:
        u = User(
            username=f"backfill_{uuid4().hex[:10]}",
            hashed_password="x",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
            sex="male",
            height_cm=170.0,
        )
        db.add(u)
        db.commit()
        return u.id


def test_without_a_birth_year_the_configured_fallback_age_is_used(
    database: None, monkeypatch: pytest.MonkeyPatch
):
    from config import settings

    monkeypatch.setattr(settings, "scale_age", 40)
    mid = _add(_user_without_birth_year(), **RAW)
    with SessionLocal() as db:
        backfill_derived(db)
    assert _get(mid).bmi is not None


def test_without_any_age_nothing_is_derived(
    database: None, monkeypatch: pytest.MonkeyPatch
):
    from config import settings

    monkeypatch.setattr(settings, "scale_age", 0)
    mid = _add(_user_without_birth_year(), **RAW)
    with SessionLocal() as db:
        backfill_derived(db)
    assert _get(mid).bmi is None
