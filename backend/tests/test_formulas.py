import pytest

from formulas import ImpedanceInputs, UserProfile, calculate_all

# ── Fixtures ──────────────────────────────────────────────────────────────────

PROFILE = UserProfile(age=34, height_cm=194, sex=1, weight_kg=85.0)

INPUTS = ImpedanceInputs(
    ra_z20=312.5,
    la_z20=308.0,
    rl_z20=210.0,
    ll_z20=208.5,
    trunk_z20=42.0,
    ra_z100=290.0,
    la_z100=287.0,
    rl_z100=195.0,
    ll_z100=193.0,
    trunk_z100=38.0,
    body_fat_pct=18.2,
)


@pytest.fixture(scope="module")
def result():
    return calculate_all(PROFILE, INPUTS)


# ── Basic metrics ─────────────────────────────────────────────────────────────


def test_bmi(result):
    expected = round(85.0 / 1.94**2, 2)
    assert result["bmi"] == expected


def test_fat_mass_is_rounded_to_one_decimal_first(result):
    """WLA25 rounds fat mass before taking lean from it (#344): 15.47 → 15.5."""
    assert result["fat_mass_kg"] == 15.5


def test_lean_mass(result):
    assert result["lean_mass_kg"] == pytest.approx(
        85.0 - result["fat_mass_kg"], abs=0.01
    )


def test_fat_free_equals_lean(result):
    assert result["fat_free_weight_kg"] == result["lean_mass_kg"]


# ── Whole body — WLA25's derivation chain (#344) ──────────────────────────────
# Everything below follows from fat-free mass (weight minus the scale's body
# fat), as in the scale's own app (Fitdays). Checked against Fitdays outside
# this repo: 39 of 45 values exact, the rest within 0.1 (or 2 kcal). Expected
# values are the formulas worked by hand, with the vendor's half-up rounding
# to one decimal:
#
#   fat = round1(w·bf)   lean = w − fat   water = lean·0.733
#   water % = water / w   muscle = lean·0.933   bone = lean·0.067
#   protein = lean·0.2    skeletal muscle = water·0.834 − 2.627
#   subcutaneous % = (bf·−0.0002 + 0.72)·bf    BMR = int(lean·21.6 + 370)

WLA25_CHAIN = [
    # (weight, bf %, height, sex), expected
    (
        (72.5, 18.5, 170, 1),
        dict(
            fat_mass_kg=13.4,
            lean_mass_kg=59.1,
            body_water_pct=59.8,
            muscle_mass_kg=55.1,
            bone_mass_kg=4.0,
            protein_kg=11.8,
            skeletal_muscle_kg=33.5,
            smi=11.59,
            subcutaneous_fat_pct=13.3,
            bmr_kcal=1646,
            body_age=38,
        ),
    ),
    (
        (95.0, 32.0, 180, 1),
        dict(
            fat_mass_kg=30.4,
            lean_mass_kg=64.6,
            body_water_pct=49.8,
            muscle_mass_kg=60.3,
            bone_mass_kg=4.3,
            protein_kg=12.9,
            skeletal_muscle_kg=36.86,
            smi=11.38,
            subcutaneous_fat_pct=22.8,
            bmr_kcal=1765,
            body_age=43,
        ),
    ),
    (
        (60.0, 30.0, 165, 0),
        dict(
            fat_mass_kg=18.0,
            lean_mass_kg=42.0,
            body_water_pct=51.3,
            muscle_mass_kg=39.2,
            bone_mass_kg=2.8,
            protein_kg=8.4,
            skeletal_muscle_kg=23.05,
            smi=8.47,
            subcutaneous_fat_pct=21.4,
            bmr_kcal=1277,
            body_age=39,
        ),
    ),
]


@pytest.mark.parametrize(("person", "expected"), WLA25_CHAIN)
def test_whole_body_follows_the_wla25_chain(person, expected):
    weight, fat_pct, height, sex = person
    r = calculate_all(
        UserProfile(age=40, height_cm=height, sex=sex, weight_kg=weight),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": fat_pct}),
    )
    assert {k: r[k] for k in expected} == expected


def test_bmr_is_whole_kcal(result):
    assert result["bmr_kcal"] == int(result["bmr_kcal"])


@pytest.mark.parametrize(
    ("sex", "fat_pct", "offset"),
    [
        # Men: under 14 % → −3 ... 33–36 % → +4, 36 % and up → +5; no 0 band.
        (1, 13.9, -3),
        (1, 14.0, -2),
        (1, 23.9, -1),
        (1, 24.0, 1),
        (1, 35.9, 4),
        (1, 36.0, 5),
        # Women: under 24 % → −3 ... 42–45 % → +4; 45–46 % is +0 (the vendor's
        # own quirk), 46 % and up → +5.
        (0, 23.9, -3),
        (0, 44.9, 4),
        (0, 45.5, 0),
        (0, 46.0, 5),
    ],
)
def test_body_age_is_age_plus_a_body_fat_band(sex, fat_pct, offset):
    r = calculate_all(
        UserProfile(age=40, height_cm=170, sex=sex, weight_kg=70.0),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": fat_pct}),
    )
    assert r["body_age"] == 40 + offset


def test_body_age_under_ten_is_the_age():
    r = calculate_all(
        UserProfile(age=9, height_cm=130, sex=1, weight_kg=30.0),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": 30.0}),
    )
    assert r["body_age"] == 9


def test_whr_is_no_longer_estimated(result):
    """Fitman's WHR estimate was far from Fitdays' (1.22 against 0.94), and
    WLA25 has no WHR formula: no number beats a wrong one (#344)."""
    assert result["whr_estimate"] is None


def test_protein_and_salt_positive(result):
    assert result["protein_kg"] > 0
    assert result["inorganic_salt_kg"] > 0


# ── Segmental consistency ─────────────────────────────────────────────────────


def test_trunk_lean_greater_than_arm_lean(result):
    # Trunk has more lean mass than any single limb
    assert result["trunk_muscle_kg"] > result["ra_muscle_kg"]


def test_trunk_fat_greater_than_arm_fat(result):
    assert result["trunk_fat_kg"] > result["ra_fat_kg"]


# ── All expected keys present ─────────────────────────────────────────────────


def test_all_fields_returned(result):
    expected_keys = [
        "bmi",
        "fat_mass_kg",
        "lean_mass_kg",
        "fat_free_weight_kg",
        "skeletal_muscle_kg",
        "body_water_pct",
        "protein_kg",
        "inorganic_salt_kg",
        "bmr_kcal",
        "visceral_fat_grade",
        "subcutaneous_fat_pct",
        "body_age",
        "whr_estimate",
        "smi",
        "muscle_mass_kg",
        "bone_mass_kg",
        "ra_muscle_kg",
        "la_muscle_kg",
        "rl_muscle_kg",
        "ll_muscle_kg",
        "trunk_muscle_kg",
        "ra_fat_kg",
        "la_fat_kg",
        "rl_fat_kg",
        "ll_fat_kg",
        "trunk_fat_kg",
    ]
    for key in expected_keys:
        assert key in result, f"Missing key: {key}"


# ── Without trunk impedance (#325) ────────────────────────────────────────────
# The scale's trunk bytes are not a usable impedance (#320), so scale weigh-ins
# store none. Only skeletal muscle (Janssen needs the whole-body path) may go
# missing because of it; everything else must still be derived.
#
# A made-up person, as everywhere in this public repo: male, 40, 170 cm,
# 72.5 kg, with the impedances of tests/scale_frames.py's result in packet
# order (bytes 16, 18, 20, 22, then 26, 28, 30, 32).

SCALE_PERSON = UserProfile(age=40, height_cm=170, sex=1, weight_kg=72.5)

NO_TRUNK = ImpedanceInputs(
    la_z20=350.0,
    ra_z20=340.0,
    rl_z20=260.0,
    ll_z20=255.0,
    trunk_z20=None,
    la_z100=320.0,
    ra_z100=310.0,
    rl_z100=235.0,
    ll_z100=230.0,
    trunk_z100=None,
    body_fat_pct=18.5,
)


def _scale(**changes) -> dict:
    return calculate_all(
        SCALE_PERSON, ImpedanceInputs(**{**NO_TRUNK.__dict__, **changes})
    )


def test_derived_metrics_do_not_need_trunk_impedance():
    r = _scale()
    for field in (
        "bmi",
        "fat_mass_kg",
        "lean_mass_kg",
        "bmr_kcal",
        "body_water_pct",
        "visceral_fat_grade",
        "body_age",
        "trunk_fat_kg",
        "trunk_muscle_kg",
        "ra_fat_kg",
        "ll_muscle_kg",
    ):
        assert r[field] is not None, field


def test_skeletal_muscle_no_longer_needs_trunk():
    """Janssen needed the whole-body path through the trunk; WLA25's skeletal
    muscle comes from body water, so scale weigh-ins get it too (#344)."""
    r = _scale()
    assert r["skeletal_muscle_kg"] == 33.5
    assert r["smi"] == 11.59


# ── iCOMON WLA25 estimates (#325) ─────────────────────────────────────────────
# Fitdays uses iCOMON's WLA25 algorithm; Fitman ports its formulas from
# sacoma-lib (MIT). Matching Fitdays was checked against real weigh-ins
# outside this repo; here the expected values are the formulas worked by hand.

WLA25_WHOLE_BODY = [
    # weight, body fat %, visceral, trunk fat kg, trunk muscle kg
    # fat = w·bf; lean = w − fat; visceral = int(lean·−0.029 + fat·0.502 − 0.477)
    # trunk fat = fat·0.552545 + 0.322704; trunk muscle = lean·0.440922 − 0.275461
    (72.5, 18.5, 4, 7.73, 25.78),
    (95.0, 32.0, 12, 17.12, 28.21),
]


@pytest.mark.parametrize(
    ("weight", "fat_pct", "visceral", "trunk_fat", "trunk_muscle"), WLA25_WHOLE_BODY
)
def test_visceral_fat_follows_wla25(weight, fat_pct, visceral, trunk_fat, trunk_muscle):
    r = calculate_all(
        UserProfile(age=40, height_cm=170, sex=1, weight_kg=weight),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": fat_pct}),
    )
    assert r["visceral_fat_grade"] == visceral


@pytest.mark.parametrize(
    ("weight", "fat_pct", "visceral", "trunk_fat", "trunk_muscle"), WLA25_WHOLE_BODY
)
def test_trunk_follows_wla25_without_trunk_terms(
    weight, fat_pct, visceral, trunk_fat, trunk_muscle
):
    """Trunk impedance terms off (#320); within ~0.6 kg of Fitdays that way."""
    r = calculate_all(
        UserProfile(age=40, height_cm=170, sex=1, weight_kg=weight),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": fat_pct}),
    )
    assert r["trunk_fat_kg"] == pytest.approx(trunk_fat, abs=0.01)
    assert r["trunk_muscle_kg"] == pytest.approx(trunk_muscle, abs=0.01)


# ── Per-limb fat and muscle: WLA25's regressions (#332) ───────────────────────
# Each limb from its own two readings (20 and 100 kHz) and whole-body fat and
# lean mass. Fitman used to share lean mass (bone and water included) across
# the limbs, which put arm "muscle" at over twice Fitdays' value. Checked
# against Fitdays outside this repo: 36 of 40 limb values exact, the rest
# within 0.2 kg. Expected values below are the regressions worked by hand for
# the made-up person (fat 13.41 kg, lean 59.09 kg).
#
#   arm fat    = z100·0.007476 + fat·0.081201 − z20·0.005752 − 0.662152
#   leg fat    = z100·0.008645 + fat·0.135438 − z20·0.00801  + 0.492479
#   arm muscle = z20·0.002847 + lean·0.058707 − z100·0.005857 + 0.561911
#   leg muscle = z100·0.008157 + lean·0.176554 − z20·0.007381 − 0.688932


def _limbs(r: dict) -> dict:
    return {
        k: r[f"{k}_kg"]
        for k in (
            "la_fat",
            "ra_fat",
            "ll_fat",
            "rl_fat",
            "la_muscle",
            "ra_muscle",
            "ll_muscle",
            "rl_muscle",
        )
    }


def test_limbs_follow_the_wla25_regressions():
    assert _limbs(_scale()) == {
        "la_fat": 0.81,
        "ra_fat": 0.79,
        "ll_fat": 2.25,
        "rl_fat": 2.26,
        "la_muscle": 3.15,
        "ra_muscle": 3.18,
        "ll_muscle": 9.74,
        "rl_muscle": 9.74,
    }


def test_arm_muscle_is_no_longer_a_share_of_lean_mass():
    """The old split gave each arm roughly lean × II share: ~8 kg here."""
    r = _scale()
    assert r["la_muscle_kg"] < 4.0
    assert r["ra_muscle_kg"] < 4.0


def test_each_limb_uses_its_own_readings():
    """Raising the left arm's 20 kHz reading moves the left arm only."""
    base, changed = _limbs(_scale()), _limbs(_scale(la_z20=360.0))
    moved = {k for k in base if base[k] != changed[k]}
    assert moved == {"la_fat", "la_muscle"}


def test_implausible_arm_asymmetry_is_reconciled():
    """Left arm fat alone would be 0.08 kg against the right's 0.79: over the
    vendor's 0.3 kg limit, so it is set from the right arm, minus
    (z20 + z100) / 20213 because its reading is the higher one."""
    r = _limbs(_scale(la_z20=450.0, la_z100=300.0))
    assert r["la_fat"] == 0.75
    assert r["ra_fat"] == 0.79


def test_asymmetry_is_reconciled_whichever_side_is_off():
    """The mirror case: the right arm's fat alone would be implausibly low."""
    r = _limbs(_scale(ra_z20=450.0, ra_z100=300.0))
    assert r["ra_fat"] == 0.77
    assert r["la_fat"] == 0.81


def test_implausible_leg_asymmetry_is_reconciled():
    """Legs use a 0.5 kg limit."""
    r = _limbs(_scale(ll_z20=330.0, ll_z100=200.0))
    assert r["ll_fat"] == 2.23
    assert r["rl_fat"] == 2.26


def test_limbs_have_a_floor():
    """At 3 % body fat the arm regressions go negative; the vendor floors fat
    at 0.1 kg plus a small impedance term."""
    r = calculate_all(
        UserProfile(age=40, height_cm=170, sex=1, weight_kg=60.0),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": 3.0}),
    )
    assert r["la_fat_kg"] == 0.13
    assert r["ra_fat_kg"] == 0.13


@pytest.mark.parametrize(("fat_pct", "expected"), [(3.0, 1), (70.0, 20)])
def test_visceral_fat_stays_on_the_1_to_20_scale(fat_pct, expected):
    r = calculate_all(
        UserProfile(age=40, height_cm=170, sex=1, weight_kg=150.0),
        ImpedanceInputs(**{**NO_TRUNK.__dict__, "body_fat_pct": fat_pct}),
    )
    assert r["visceral_fat_grade"] == expected


def test_limb_muscle_has_a_floor():
    """A left-arm 100 kHz reading of 1000 Ω drives its muscle regression
    negative; the floor is 0.2 kg plus (z20 + z100) / 20113."""
    assert _limbs(_scale(la_z100=1000.0))["la_muscle"] == 0.27
