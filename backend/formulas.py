"""
BIA body composition formulae.

⚠️  Medical disclaimer: All calculated metrics are ESTIMATES derived from
published research formulae. The developers are not medical professionals.
These values are not clinically validated and must not be used for medical
diagnosis or treatment. Always consult a qualified healthcare professional.

Results will differ from Fitdays, which uses proprietary undisclosed algorithms.

Sources:
  Janssen (2000)    doi:10.1152/jappl.2000.89.2.465
  Watson (1980)     Am J Clin Nutr. 33(1):27-39
  Katch-McArdle     Exercise Physiology, McArdle et al. 1996
  Wang (1999)       Am J Clin Nutr. 69(5):833-841
  WLA25             iCOMON's body-composition algorithm (used by Fitdays for this
                    scale), ported from sacoma-lib (MIT, github.com/ynsgnr/sacoma-lib):
                    visceral fat, trunk fat and trunk muscle (#325)
"""

from dataclasses import dataclass


@dataclass
class UserProfile:
    age: int
    height_cm: float
    sex: int  # 1 = male, 0 = female
    weight_kg: float


@dataclass
class ImpedanceInputs:
    ra_z20: float  # Right arm 20 kHz (Ω)
    la_z20: float  # Left arm 20 kHz (Ω)
    rl_z20: float  # Right leg 20 kHz (Ω)
    ll_z20: float  # Left leg 20 kHz (Ω)
    trunk_z20: float | None  # Trunk 20 kHz (Ω); None for scale weigh-ins (#320)
    ra_z100: float
    la_z100: float
    rl_z100: float
    ll_z100: float
    trunk_z100: float | None
    body_fat_pct: float  # Scale's own BIA result (FFB3 bytes 40-41)


def _r(x: float) -> float:
    return round(x, 2)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def calculate_all(profile: UserProfile, inputs: ImpedanceInputs) -> dict:
    """
    Derive all body composition metrics from a user profile and BIA inputs.
    Returns a dict of fields matching BodyMeasurement column names.
    """
    h_m = profile.height_cm / 100
    w = profile.weight_kg
    fat_pct = inputs.body_fat_pct

    # ── Basic ──────────────────────────────────────────────────────────────────
    bmi = _r(w / h_m**2)
    fat_mass_kg = _r(w * fat_pct / 100)
    lean_mass_kg = _r(w - fat_mass_kg)
    fat_free_weight_kg = lean_mass_kg

    # ── BMR — Katch-McArdle (1996) ─────────────────────────────────────────────
    bmr_kcal = _r(370 + 21.6 * lean_mass_kg)

    # ── Total Body Water — Watson (1980) ───────────────────────────────────────
    # Male:   TBW = 2.447 − 0.09156×age + 0.1074×height_cm + 0.3362×weight_kg
    # Female: TBW = −2.097 + 0.1069×height_cm + 0.2466×weight_kg
    if profile.sex == 1:
        tbw_kg = 2.447 - 0.09156 * profile.age + 0.1074 * profile.height_cm + 0.3362 * w
    else:
        tbw_kg = -2.097 + 0.1069 * profile.height_cm + 0.2466 * w
    tbw_kg = max(0.0, tbw_kg)
    body_water_pct = _r(tbw_kg / w * 100)

    # ── Protein and mineral mass — Wang (1999) ─────────────────────────────────
    # Five-compartment model fractions of lean mass:
    # water ≈ 73%, protein ≈ 19%, minerals ≈ 6%
    protein_kg = _r(lean_mass_kg * 0.19)
    inorganic_salt_kg = _r(lean_mass_kg * 0.06)

    # ── Skeletal Muscle Mass — Janssen (2000) ──────────────────────────────────
    # SMM (kg) = (H²/R × 0.401) + (sex × 3.825) − (age × 0.071) + 5.102
    # H = height in cm; R = whole-body resistance (Ω)
    # Approximated from the right-side BIA path at 20 kHz (paper used 50 kHz
    # wrist-to-ankle; 20 kHz gives a conservative overestimate of resistance).
    # Needs the whole-body path through the trunk, so it is left empty when
    # trunk impedance is unknown — as for scale weigh-ins (#320, #325).
    skeletal_muscle_kg: float | None = None
    smi: float | None = None
    if inputs.trunk_z20 is not None:
        R = inputs.ra_z20 + inputs.trunk_z20 + inputs.rl_z20
        smm = (
            (profile.height_cm**2 / R * 0.401)
            + (profile.sex * 3.825)
            - (profile.age * 0.071)
            + 5.102
        )
        skeletal_muscle_kg = _r(max(0.0, smm))
        # SMI — Skeletal Muscle Index (kg/m²); low SMI flags sarcopenia risk
        smi = _r(skeletal_muscle_kg / h_m**2)

    # ── Visceral fat grade — iCOMON WLA25 ─────────────────────────────────────
    # Hand and foot electrodes cannot localise abdominal fat; every consumer
    # scale estimates it from whole-body fat and lean mass. WLA25 is the one
    # this scale's own app uses, truncated to a 1–20 grade. It reproduced
    # Fitdays exactly on both readings checked (9 and 16).
    grade = int(lean_mass_kg * -0.029 + fat_mass_kg * 0.502 - 0.477)
    visceral_fat_grade = float(_clamp(grade, 1, 20))

    # ── Subcutaneous fat % ─────────────────────────────────────────────────────
    # Subcutaneous fat ≈ 85% of total fat (Shen 2003).
    subcutaneous_fat_pct = _r(fat_pct * 0.85)

    # ── Body age estimate ──────────────────────────────────────────────────────
    # Compares body_fat_pct to ACSM age/sex norms (men ~15%, women ~23%).
    ref_fat = 15.0 if profile.sex == 1 else 23.0
    body_age = round(_clamp(profile.age + (fat_pct - ref_fat) * 0.5, 15, 99))

    # ── WHR estimate ───────────────────────────────────────────────────────────
    # Waist and hip estimated from anthropometrics + trunk/leg fat fraction.
    # Based on Heitmann (1990) and Lean (1995) trunk fat / waist correlations.
    # Values are rough estimates only.
    trunk_fat_est = fat_mass_kg * 0.42
    waist_cm = (
        0.84 * profile.height_cm
        - 0.18 * w
        + 0.22 * (trunk_fat_est / w * 100)
        + (5.0 if profile.sex == 1 else 0.0)
    )
    leg_fat_est = fat_mass_kg * 0.34
    hip_cm = (
        0.67 * profile.height_cm
        - 0.10 * w
        + 0.25 * (leg_fat_est / w * 100)
        + (2.0 if profile.sex == 1 else 5.0)
    )
    whr_estimate = _r(waist_cm / hip_cm)

    # ── Segmental — WLA25 ─────────────────────────────────────────────────────
    # Trunk fat and trunk muscle use WLA25's regressions with the trunk-
    # impedance terms off: the scale's trunk bytes are not a usable impedance
    # (#320), and in WLA25 those terms only nudge a value dominated by
    # whole-body fat and lean mass (within ~0.6 kg of Fitdays without them).
    trunk_fat = _clamp(fat_mass_kg * 0.552545 + 0.322704, 0.1, fat_mass_kg)
    trunk_lean = _clamp(lean_mass_kg * 0.440922 - 0.275461, 0.7, lean_mass_kg)
    seg_fat, seg_lean = _wla25_limbs(fat_mass_kg, lean_mass_kg, inputs)
    seg_fat["trunk"] = _r(trunk_fat)
    seg_lean["trunk"] = _r(trunk_lean)

    return {
        "bmi": bmi,
        "fat_mass_kg": fat_mass_kg,
        "lean_mass_kg": lean_mass_kg,
        "fat_free_weight_kg": fat_free_weight_kg,
        "skeletal_muscle_kg": skeletal_muscle_kg,
        "body_water_pct": body_water_pct,
        "protein_kg": protein_kg,
        "inorganic_salt_kg": inorganic_salt_kg,
        "bmr_kcal": bmr_kcal,
        "visceral_fat_grade": visceral_fat_grade,
        "subcutaneous_fat_pct": subcutaneous_fat_pct,
        "body_age": body_age,
        "whr_estimate": whr_estimate,
        "smi": smi,
        "ra_muscle_kg": seg_lean["ra"],
        "la_muscle_kg": seg_lean["la"],
        "rl_muscle_kg": seg_lean["rl"],
        "ll_muscle_kg": seg_lean["ll"],
        "trunk_muscle_kg": seg_lean["trunk"],
        "ra_fat_kg": seg_fat["ra"],
        "la_fat_kg": seg_fat["la"],
        "rl_fat_kg": seg_fat["rl"],
        "ll_fat_kg": seg_fat["ll"],
        "trunk_fat_kg": seg_fat["trunk"],
    }


def _wla25_limbs(
    fat: float, lean: float, z: ImpedanceInputs
) -> tuple[dict[str, float], dict[str, float]]:
    """Per-limb fat and muscle: WLA25's regressions, each limb from its own
    20 and 100 kHz readings (#332). Coefficients, the left/right reconciliation
    and the floors, with their three divisors, are the vendor's as ported by
    sacoma-lib; they reproduce Fitdays' limb values within 0.2 kg."""
    arm_fat = {
        side: z100 * 0.007476 + (fat * 0.081201 - z20 * 0.005752) - 0.662152
        for side, z20, z100 in (
            ("la", z.la_z20, z.la_z100),
            ("ra", z.ra_z20, z.ra_z100),
        )
    }
    leg_fat = {
        side: z100 * 0.008645 + (fat * 0.135438 - z20 * 0.00801) + 0.492479
        for side, z20, z100 in (
            ("ll", z.ll_z20, z.ll_z100),
            ("rl", z.rl_z20, z.rl_z100),
        )
    }
    _reconcile(arm_fat, "la", "ra", z.la_z20, z.ra_z20, z.la_z100, z.ra_z100, 0.3)
    _reconcile(leg_fat, "ll", "rl", z.ll_z20, z.rl_z20, z.ll_z100, z.rl_z100, 0.5)
    muscle = {
        "la": z.la_z20 * 0.002847 + lean * 0.058707 - z.la_z100 * 0.005857 + 0.561911,
        "ra": z.ra_z20 * 0.002847 + lean * 0.058707 - z.ra_z100 * 0.005857 + 0.561911,
        "ll": z.ll_z100 * 0.008157 + (lean * 0.176554 - z.ll_z20 * 0.007381) - 0.688932,
        "rl": z.rl_z100 * 0.008157 + (lean * 0.176554 - z.rl_z20 * 0.007381) - 0.688932,
    }
    fat_by_limb = {**arm_fat, **leg_fat}

    # Floors: left limbs divide by 20113, right limbs by 20213 (vendor's own).
    readings = {
        "la": (z.la_z20 + z.la_z100) / 20113,
        "ra": (z.ra_z20 + z.ra_z100) / 20213,
        "ll": (z.ll_z20 + z.ll_z100) / 20113,
        "rl": (z.rl_z20 + z.rl_z100) / 20213,
    }
    for limb, term in readings.items():
        if fat_by_limb[limb] < 0.1:
            fat_by_limb[limb] = term + 0.1
        if muscle[limb] < 0.2:
            muscle[limb] = term + 0.2
    return (
        {k: _r(v) for k, v in fat_by_limb.items()},
        {k: _r(v) for k, v in muscle.items()},
    )


def _reconcile(
    fat: dict[str, float],
    left: str,
    right: str,
    z20_left: float,
    z20_right: float,
    z100_left: float,
    z100_right: float,
    limit: float,
) -> None:
    """Set an implausibly different side from the other: the lower side takes
    the higher one's value, nudged by (z20 + z100) / 20213, up if its 20 kHz
    reading is the lower of the two, down otherwise."""
    if abs(fat[right] - fat[left]) <= limit:
        return
    if fat[right] <= fat[left]:
        t = (z20_right + z100_right) / 20213
        fat[right] = (t if z20_right <= z20_left else -t) + fat[left]
    else:
        t = (z20_left + z100_left) / 20213
        fat[left] = (t if z20_left <= z20_right else -t) + fat[right]
