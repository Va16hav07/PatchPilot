"""Small hand-curated additions on top of IFCT and INDB.

Every value here is cited. Keep this list short: it fills gaps in the
official sources, it does not replace them.
"""

from app.nutrition import nutrients as N

# Everyday names that neither source carries.
ALIASES: dict[str, list[str]] = {
    "ifct:B021": ["Toor dal", "Tuvar dal", "Arhar"],
    "ifct:B010": ["Moong dal"],
    "ifct:B001": ["Chana dal"],
    "indb:ASC096": ["Roti", "Phulka", "Chapati"],
    "indb:ASC113": ["Plain rice", "Cooked rice", "Chawal", "Bhaat"],
    "indb:ASC001": ["Chai", "Tea"],
}

# Staples missing from IFCT 2017 and INDB. Source: USDA FoodData Central
# (public domain), SR Legacy, values per 100 g.
USDA_FOODS: list[dict] = [
    {
        "_id": "usda:171284",
        "source": "USDA",
        "source_code": "171284",
        "kind": "ingredient",
        "name": "Curd (plain yogurt, whole milk)",
        "local_names": ["Dahi", "Curd", "Thayir", "Perugu", "Mosaru"],
        "group": "Milk and Milk Products",
        "diet_tags": ["vegetarian"],
        "per_100g": N.rounded({
            **N.zero(),
            "energy_kcal": 61.0, "protein_g": 3.47, "fat_g": 3.25, "carb_g": 4.66, "fibre_g": 0.0,
            "sat_fat_g": 2.096, "cholesterol_mg": 13.0, "calcium_mg": 121.0, "iron_mg": 0.05,
            "magnesium_mg": 12.0, "phosphorus_mg": 95.0, "potassium_mg": 155.0, "sodium_mg": 46.0,
            "zinc_mg": 0.59, "vit_b1_mg": 0.029, "vit_b2_mg": 0.142, "vit_b3_mg": 0.075,
            "vit_b6_mg": 0.032, "folate_ug": 7.0, "vit_c_mg": 0.5,
        }),
        "density_g_per_ml": 1.03,
        "quality_flags": [],
        "quarantined": False,
    },
]


# Common dishes INDB lacks, derived from an INDB recipe by swapping one
# ingredient for its IFCT equivalent. (base dish, swap out, swap in, grams per serving)
DERIVED_DISHES: list[dict] = [
    {
        "_id": "curated:toor-dal-tadka",
        "name": "Toor dal tadka (Arhar dal / Tuvar dal)",
        "local_names": ["Toor dal", "Arhar dal", "Tuvar dal", "Dal tadka", "Yellow dal", "Plain dal"],
        "base": "indb:ASC151",  # Washed moong dal: dal, cumin, turmeric, spices, 1 tsp oil, water
        "swap_out": "ifct:B010",  # Green gram, dal
        "swap_in": "ifct:B021",  # Red gram, dal
        "grams": 30.0,  # dal per serving in the base recipe (1 recipe = 1 bowl)
    },
]


def _derive(spec: dict, by_id: dict[str, dict]) -> dict:
    base, out_food, in_food = by_id[spec["base"]], by_id[spec["swap_out"]], by_id[spec["swap_in"]]
    if base["quarantined"]:
        raise ValueError(f"base dish {spec['base']} is quarantined")
    g = spec["grams"]
    swapped = N.add(N.scale(in_food["per_100g"], g / 100), N.scale(out_food["per_100g"], -g / 100))
    nutrients = N.add(base["serving"]["nutrients"], swapped)
    ingredients = [
        {**i, "name": in_food["name"], "code": in_food["source_code"]} if i.get("code") == out_food["source_code"] else i
        for i in base["ingredients"]
    ]
    return {
        "_id": spec["_id"],
        "source": "INDB",
        "source_code": None,
        "derived_from": spec["base"],
        "kind": "dish",
        "name": spec["name"],
        "local_names": spec["local_names"],
        "recipe_source": f"{base['name']} ({spec['base']}) with {out_food['name']} replaced by {in_food['name']}",
        "serving": {**base["serving"], "nutrients": N.rounded(nutrients)},
        "per_100g_raw_basis": None,
        "ingredients": ingredients,
        "quality_flags": ["curated_derived_recipe"],
        "quarantined": False,
    }


def apply(docs: list[dict]) -> list[dict]:
    by_id = {d["_id"]: d for d in docs}
    for food_id, names in ALIASES.items():
        food = by_id.get(food_id)
        if food is None:
            raise KeyError(f"alias target {food_id} not found")
        existing = {n.lower() for n in food["local_names"]}
        food["local_names"] += [n for n in names if n.lower() not in existing]
    return docs + USDA_FOODS + [_derive(spec, by_id) for spec in DERIVED_DISHES]
