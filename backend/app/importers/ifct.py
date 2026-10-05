"""IFCT 2017 (ICMR-NIN) -> food documents.

Source: the `compositions/index.csv` of the `ifct2017` package, which
transcribes IFCT 2017. Energy is in kJ, every other value in grams per 100 g
edible portion.
"""

import csv
import re
from collections.abc import Iterable

from app.nutrition import nutrients as N

SOURCE = "IFCT2017"

# IFCT 2017 energy conversion factors, kJ per g.
KJ_PER_G = {"protcnt": 17.0, "fatce": 37.0, "choavldf": 17.0, "fibtg": 8.0}

# column -> (our key, multiplier from g/100g to our unit)
COLUMN_MAP: dict[str, tuple[str, float]] = {
    "protcnt": ("protein_g", 1),
    "choavldf": ("carb_g", 1),
    "fatce": ("fat_g", 1),
    "fibtg": ("fibre_g", 1),
    "fsugar": ("sugar_g", 1),
    "fasat": ("sat_fat_g", 1),
    "cholc": ("cholesterol_mg", 1e3),
    "ca": ("calcium_mg", 1e3),
    "fe": ("iron_mg", 1e3),
    "mg": ("magnesium_mg", 1e3),
    "p": ("phosphorus_mg", 1e3),
    "k": ("potassium_mg", 1e3),
    "na": ("sodium_mg", 1e3),
    "zn": ("zinc_mg", 1e3),
    "thia": ("vit_b1_mg", 1e3),
    "ribf": ("vit_b2_mg", 1e3),
    "nia": ("vit_b3_mg", 1e3),
    "vitb6c": ("vit_b6_mg", 1e3),
    "folsum": ("folate_ug", 1e6),
    "vitc": ("vit_c_mg", 1e3),
}

# Food groups measured by volume in Indian kitchens, with density in g/ml.
GROUP_DENSITY = {
    "Edible Oils and Fats": 0.92,
}
CODE_DENSITY = {"L001": 1.03, "L002": 1.03}  # buffalo milk, cow milk

# Flag energy that disagrees with the macros by more than both of these...
FLAG_REL, FLAG_ABS_KCAL = 0.15, 15.0
# ...and replace it when the gap is this large: a transcription error, e.g.
# chicken leg listed at 1605 kJ (384 kcal) while its macros give 191 kcal.
# Smaller gaps are mostly IFCT not counting energy from fibre.
CORRECT_REL, CORRECT_ABS_KCAL = 0.40, 40.0


def _num(value: str | None) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except ValueError:
        return 0.0


_LANG_PREFIX = re.compile(r"^(?:[A-Z][a-z]*\.,?\s*)+")


def parse_local_names(lang: str) -> list[str]:
    """'A. Moricha guti; H. Ramdana; E. Mung bean, Moong.' -> ['Moricha guti', 'Ramdana', 'Mung bean', 'Moong']"""
    names: list[str] = []
    for part in (lang or "").split(";"):
        for name in _LANG_PREFIX.sub("", part.strip()).split(","):
            name = name.strip(" .")
            if name and name.lower() not in (n.lower() for n in names):
                names.append(name)
    return names


def energy_from_macros_kcal(row: dict) -> float:
    kj = sum(_num(row.get(col)) * f for col, f in KJ_PER_G.items())
    return kj * N.KCAL_PER_KJ


def _differs(reported: float, computed: float, rel: float, abs_kcal: float) -> bool:
    gap = abs(reported - computed)
    return computed > 0 and gap / computed > rel and gap > abs_kcal


def row_to_food(row: dict) -> dict:
    per_100g = N.zero()
    for col, (key, mult) in COLUMN_MAP.items():
        per_100g[key] = _num(row.get(col)) * mult

    flags: list[str] = []
    reported_kcal = _num(row.get("enerc")) * N.KCAL_PER_KJ
    computed_kcal = energy_from_macros_kcal(row)
    if reported_kcal <= 0 and computed_kcal > 0:
        per_100g["energy_kcal"] = computed_kcal
        flags.append("energy_recomputed_from_macros")
    elif _differs(reported_kcal, computed_kcal, CORRECT_REL, CORRECT_ABS_KCAL):
        per_100g["energy_kcal"] = computed_kcal
        flags.append("energy_corrected_from_macros")
    else:
        per_100g["energy_kcal"] = reported_kcal
        if _differs(reported_kcal, computed_kcal, FLAG_REL, FLAG_ABS_KCAL):
            flags.append("energy_mismatch")

    code = row["code"].strip()
    group = row.get("grup", "").strip()
    density = CODE_DENSITY.get(code, GROUP_DENSITY.get(group))
    return {
        "_id": f"ifct:{code}",
        "source": SOURCE,
        "source_code": code,
        "kind": "ingredient",
        "name": row["name"].strip(),
        "scientific_name": row.get("scie", "").strip() or None,
        "local_names": parse_local_names(row.get("lang", "")),
        "group": group,
        "diet_tags": (row.get("tags") or "").split(),
        "per_100g": N.rounded(per_100g),
        "density_g_per_ml": density,
        "quality_flags": flags,
        "quarantined": False,
    }


def load(lines: Iterable[str]) -> list[dict]:
    return [row_to_food(row) for row in csv.DictReader(lines)]
