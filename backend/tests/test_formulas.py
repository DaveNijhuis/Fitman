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


def test_fat_mass(result):
    assert result["fat_mass_kg"] == pytest.approx(85.0 * 18.2 / 100, abs=0.01)


def test_lean_mass(result):
    assert result["lean_mass_kg"] == pytest.approx(
        85.0 - result["fat_mass_kg"], abs=0.01
    )


def test_fat_free_equals_lean(result):
    assert result["fat_free_weight_kg"] == result["lean_mass_kg"]


# ── BMR ───────────────────────────────────────────────────────────────────────


def test_bmr_katch_mcardle(result):
    expected = round(370 + 21.6 * result["lean_mass_kg"], 2)
    assert result["bmr_kcal"] == expected


# ── Watson TBW ────────────────────────────────────────────────────────────────


def test_body_water_pct_male_in_range(result):
    # Healthy adult male TBW typically 50–70%
    assert 45 < result["body_water_pct"] < 75


def test_body_water_pct_female():
    profile_f = UserProfile(age=30, height_cm=165, sex=0, weight_kg=65.0)
    res = calculate_all(profile_f, INPUTS)
    assert 40 < res["body_water_pct"] < 70


# ── Janssen SMM ───────────────────────────────────────────────────────────────


def test_skeletal_muscle_kg_positive(result):
    assert result["skeletal_muscle_kg"] > 0


def test_skeletal_muscle_kg_reasonable(result):
    # SMM should be 30–60% of body weight for a healthy adult
    assert (
        0.25 * PROFILE.weight_kg
        < result["skeletal_muscle_kg"]
        < 0.65 * PROFILE.weight_kg
    )


def test_smi_positive(result):
    assert result["smi"] > 0


# ── Derived fields ────────────────────────────────────────────────────────────


def test_visceral_fat_grade_in_range(result):
    assert 1 <= result["visceral_fat_grade"] <= 59


def test_body_age_in_range(result):
    assert 15 <= result["body_age"] <= 99


def test_whr_estimate_plausible(result):
    # Healthy WHR for males typically 0.80–1.00
    assert 0.6 < result["whr_estimate"] < 1.3


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


def test_skeletal_muscle_needs_trunk_so_is_left_empty():
    r = _scale()
    assert r["skeletal_muscle_kg"] is None
    assert r["smi"] is None


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
