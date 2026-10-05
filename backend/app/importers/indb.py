"""INDB (Indian Nutrient Databank) recipes -> dish documents.

Source: github.com/lindsayjaacks/Indian-Nutrient-Databank-INDB- (INDB.xlsx,
recipes.xlsx, recipes_servingsize.xlsx). No license is published, so the raw
files are downloaded locally and never committed.

We use INDB's per-unit-serving values. Its per-100 g values are on a
raw-ingredient-weight basis and are kept only for reference.

Quality gates (a failing dish is quarantined: stored, but hidden from search):
- deep-frying oil counted as eaten (e.g. "2 C" of fat in a pulao -> 4,876 kcal)
- missing core per-serving values
- per-serving energy disagreeing with its own macros
- implausible per-serving energy
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence

from app.nutrition import nutrients as N
from app.nutrition.engine import container_ml_for

SOURCE = "INDB"

# INDB column suffix -> (our key, multiplier)
COLUMN_MAP: dict[str, tuple[str, float]] = {
    "energy_kcal": ("energy_kcal", 1),
    "protein_g": ("protein_g", 1),
    "carb_g": ("carb_g", 1),
    "fat_g": ("fat_g", 1),
    "fibre_g": ("fibre_g", 1),
    "freesugar_g": ("sugar_g", 1),
    "sfa_mg": ("sat_fat_g", 1e-3),
    "cholesterol_mg": ("cholesterol_mg", 1),
    "calcium_mg": ("calcium_mg", 1),
    "iron_mg": ("iron_mg", 1),
    "magnesium_mg": ("magnesium_mg", 1),
    "phosphorus_mg": ("phosphorus_mg", 1),
    "potassium_mg": ("potassium_mg", 1),
    "sodium_mg": ("sodium_mg", 1),
    "zinc_mg": ("zinc_mg", 1),
    "vitb1_mg": ("vit_b1_mg", 1),
    "vitb2_mg": ("vit_b2_mg", 1),
    "vitb3_mg": ("vit_b3_mg", 1),
    "vitb6_mg": ("vit_b6_mg", 1),
    "folate_ug": ("folate_ug", 1),
    "vitc_mg": ("vit_c_mg", 1),
}
CORE = ("energy_kcal", "protein_g", "carb_g", "fat_g")

FAT_DENSITY = 0.92  # g/ml, oils and melted fats
UNIT_ML = {"ml": 1.0, "tsp": 5.0, "tbsp": 15.0, "c": 240.0}
FRYING_OIL_ML = 200.0  # this much fat in one recipe means it was used for deep frying
MAX_SERVING_KCAL = 1500.0
ENERGY_TOLERANCE = 0.20

_FAT_NAME = re.compile(r"\b(oil|ghee|butter|vanaspati|margarine|fat)\b", re.I)


def _is_added_fat(food_code: str | None, food_name: str | None) -> bool:
    code = str(food_code or "")
    if code.startswith("T"):  # IFCT group T: edible oils and fats
        return True
    return bool(_FAT_NAME.search(str(food_name or ""))) and "peanut butter" not in str(food_name).lower()


def fat_grams(amount: float | None, unit: str | None) -> float | None:
    if amount is None:
        return None
    unit = (unit or "").strip().lower()
    if unit == "g":
        return float(amount)
    if unit in UNIT_ML:
        return float(amount) * UNIT_ML[unit] * FAT_DENSITY
    return None


def _rows(sheet_rows: Iterable[Sequence]) -> list[dict]:
    it = iter(sheet_rows)
    header = [str(h) for h in next(it)]
    return [dict(zip(header, row)) for row in it if any(v is not None for v in row)]


def build(
    indb_rows: Iterable[Sequence],
    recipe_rows: Iterable[Sequence],
    serving_rows: Iterable[Sequence],
) -> list[dict]:
    nutrients = _rows(indb_rows)
    servings = {r["recipe_code"]: r for r in _rows(serving_rows)}
    ingredients: dict[str, list[dict]] = defaultdict(list)
    for r in _rows(recipe_rows):
        ingredients[r["recipe_code"]].append(r)
    return [_dish(n, servings.get(n["food_code"]), ingredients[n["food_code"]]) for n in nutrients]


def _dish(row: dict, serving_info: dict | None, ings: list[dict]) -> dict:
    code = row["food_code"]
    flags: list[str] = []

    per_serving = N.zero()
    missing = []
    for col, (key, mult) in COLUMN_MAP.items():
        v = row.get(f"unit_serving_{col}")
        if v is None:
            if key in CORE:
                missing.append(key)
            continue
        per_serving[key] = float(v) * mult
    if missing:
        flags.append("missing_core_values")

    per_100g_raw = N.zero()
    for col, (key, mult) in COLUMN_MAP.items():
        v = row.get(col)
        if v is not None:
            per_100g_raw[key] = float(v) * mult

    # Recipe yield in serving units, to turn whole-recipe fat into per-unit fat.
    units_in_recipe = None
    if serving_info:
        n_serv, size = serving_info.get("no_of_servings"), serving_info.get("size_of_servings")
        if isinstance(n_serv, (int, float)) and isinstance(size, (int, float)) and n_serv * size > 0:
            units_in_recipe = float(n_serv) * float(size)

    added_fat_total = 0.0
    fat_unknown = False
    for ing in ings:
        if not _is_added_fat(ing.get("food_code"), ing.get("food_name")):
            continue
        grams = fat_grams(ing.get("amount"), ing.get("unit"))
        if grams is None:
            fat_unknown = True
            continue
        text = f"{ing.get('ingredient_name_org', '')} {ing.get('unit_org', '')}".lower()
        if "fry" in text or grams >= FRYING_OIL_ML * FAT_DENSITY:
            flags.append("deep_frying_oil_counted")
        added_fat_total += grams

    added_fat = None
    if units_in_recipe and not fat_unknown:
        added_fat = added_fat_total / units_in_recipe
        if added_fat > per_serving["fat_g"] * 1.05 + 0.5:
            flags.append("added_fat_exceeds_total_fat")
            added_fat = None

    kcal = per_serving["energy_kcal"]
    from_macros = per_serving["protein_g"] * 4 + per_serving["carb_g"] * 4 + per_serving["fat_g"] * 9 + per_serving["fibre_g"] * 2
    if kcal > MAX_SERVING_KCAL:
        flags.append("implausible_serving_energy")
    if from_macros > 0 and abs(kcal - from_macros) / from_macros > ENERGY_TOLERANCE:
        flags.append("energy_mismatch")

    unit = (row.get("servings_unit") or "serving").strip()
    quarantine_flags = {"deep_frying_oil_counted", "missing_core_values", "implausible_serving_energy", "energy_mismatch"}
    name = str(row["food_name"]).strip()
    return {
        "_id": f"indb:{code}",
        "source": SOURCE,
        "source_code": code,
        "kind": "dish",
        "name": name,
        "local_names": _names_in_brackets(name),
        "recipe_source": row.get("primarysource"),
        "serving": {
            "unit": unit,
            "container_ml": container_ml_for(unit),
            "nutrients": N.rounded(per_serving),
            "added_fat_g": round(added_fat, 2) if added_fat is not None else None,
        },
        "per_100g_raw_basis": N.rounded(per_100g_raw),
        "ingredients": [
            {"name": i.get("food_name"), "code": i.get("food_code"), "amount": i.get("amount"), "unit": i.get("unit")}
            for i in ings
        ],
        "quality_flags": sorted(set(flags)),
        "quarantined": bool(quarantine_flags & set(flags)),
    }


def _names_in_brackets(name: str) -> list[str]:
    """'Potato cauliflower (Aloo gobhi)' -> ['Aloo gobhi']"""
    return [m.strip() for m in re.findall(r"\(([^)]+)\)", name) if m.strip()]
