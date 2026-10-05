"""The nutrients we track, and small helpers for nutrient dicts.

All nutrient dicts use these keys. Values are absolute amounts (for a portion)
or per-100 g / per-serving amounts (on a food), always in the unit below.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Nutrient:
    key: str
    label: str
    unit: str


NUTRIENTS: tuple[Nutrient, ...] = (
    Nutrient("energy_kcal", "Energy", "kcal"),
    Nutrient("protein_g", "Protein", "g"),
    Nutrient("carb_g", "Carbohydrate", "g"),
    Nutrient("fat_g", "Fat", "g"),
    Nutrient("fibre_g", "Fibre", "g"),
    Nutrient("sugar_g", "Free sugars", "g"),
    Nutrient("sat_fat_g", "Saturated fat", "g"),
    Nutrient("cholesterol_mg", "Cholesterol", "mg"),
    Nutrient("calcium_mg", "Calcium", "mg"),
    Nutrient("iron_mg", "Iron", "mg"),
    Nutrient("magnesium_mg", "Magnesium", "mg"),
    Nutrient("phosphorus_mg", "Phosphorus", "mg"),
    Nutrient("potassium_mg", "Potassium", "mg"),
    Nutrient("sodium_mg", "Sodium", "mg"),
    Nutrient("zinc_mg", "Zinc", "mg"),
    Nutrient("vit_b1_mg", "Thiamine (B1)", "mg"),
    Nutrient("vit_b2_mg", "Riboflavin (B2)", "mg"),
    Nutrient("vit_b3_mg", "Niacin (B3)", "mg"),
    Nutrient("vit_b6_mg", "Vitamin B6", "mg"),
    Nutrient("folate_ug", "Folate", "µg"),
    Nutrient("vit_c_mg", "Vitamin C", "mg"),
)
# Deliberately not tracked yet:
# - Vitamin A: the IFCT package's `vita` adds β-carotene to retinol 1:1, which
#   overstates vitamin A activity; needs proper RAE conversion first.
# - Vitamin D: IFCT reports implausibly high D2 for many plant foods.
# - Vitamin B12: present in neither IFCT 2017 nor INDB.

KEYS: tuple[str, ...] = tuple(n.key for n in NUTRIENTS)

KCAL_PER_KJ = 1 / 4.184
FAT_KCAL_PER_G = 9.0


def zero() -> dict[str, float]:
    return {k: 0.0 for k in KEYS}


def scale(values: dict[str, float], factor: float) -> dict[str, float]:
    return {k: values.get(k, 0.0) * factor for k in KEYS}


def add(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {k: a.get(k, 0.0) + b.get(k, 0.0) for k in KEYS}


def rounded(values: dict[str, float]) -> dict[str, float]:
    """Round for storage/display: kcal to whole numbers, everything else to 2 dp."""
    return {k: round(v) if k == "energy_kcal" else round(v, 2) for k, v in values.items()}
