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
    trunk_z20: float  # Trunk 20 kHz (Ω)
    ra_z100: float
    la_z100: float
    rl_z100: float
    ll_z100: float
    trunk_z100: float
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

    # ── Visceral fat grade (approximation) ────────────────────────────────────
    # No standard BIA-to-grade formula is published; consumer scales use
    # proprietary algorithms. This correlates grade 1–59 with BMI + fat % + age.
    grade = (bmi * 0.45) + (fat_pct * 0.25) + (profile.age * 0.10) - 10
    visceral_fat_grade = _r(_clamp(grade, 1.0, 59.0))

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

    # ── Segmental lean mass ────────────────────────────────────────────────────
    # Impedance index for each segment: II = H² / Z (20 kHz)
    # Lean mass distributed proportionally to II (Janssen 2002).
    h2 = profile.height_cm**2
    ii = {
        "ra": h2 / inputs.ra_z20,
        "la": h2 / inputs.la_z20,
        "rl": h2 / inputs.rl_z20,
        "ll": h2 / inputs.ll_z20,
        "trunk": h2 / inputs.trunk_z20,
    }
    ii_total = sum(ii.values())
    seg_lean = {k: _r(lean_mass_kg * v / ii_total) for k, v in ii.items()}

    # ── Segmental fat mass ─────────────────────────────────────────────────────
    # Relative fat density by segment (Wang 2001):
    # arms ≈ 65% of average density, legs ≈ 100%, trunk ≈ 140%.
    fat_density = {"ra": 0.65, "la": 0.65, "rl": 1.0, "ll": 1.0, "trunk": 1.4}
    fd_total = sum(fat_density.values())
    seg_fat = {k: _r(fat_mass_kg * v / fd_total) for k, v in fat_density.items()}

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
