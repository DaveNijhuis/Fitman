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


def test_segmental_lean_sums_to_total(result):
    total = sum(result[f"{s}_muscle_kg"] for s in ["ra", "la", "rl", "ll", "trunk"])
    assert total == pytest.approx(result["lean_mass_kg"], abs=0.1)


def test_segmental_fat_sums_to_total(result):
    total = sum(result[f"{s}_fat_kg"] for s in ["ra", "la", "rl", "ll", "trunk"])
    assert total == pytest.approx(result["fat_mass_kg"], abs=0.1)


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
