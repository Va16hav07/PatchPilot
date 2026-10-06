import io

import pytest

from app.importers import ifct, indb

IFCT_CSV = """code,name,scie,lang,grup,regn,tags,enerc,protcnt,fatce,choavldf,fibtg,fe,ca
A019,"Wheat flour, atta",Triticum aestivum,"E. Wheat; H. Atta; Tam. Godhumai maavu.",Cereals and Millets,6,vegetarian veg,1340,10.57,1.53,64.17,11.36,0.0041,0.03094
T013,Ghee,,,Edible Oils and Fats,6,vegetarian,0,0,100,0,0,0,0
N001,"Chicken, poultry, leg, skinless",,,Poultry,6,nonveg,1605,19.44,12.64,0,0,0.001,0.01
"""


@pytest.fixture
def ifct_foods():
    return {f["source_code"]: f for f in ifct.load(io.StringIO(IFCT_CSV))}


def test_ifct_units_converted(ifct_foods):
    atta = ifct_foods["A019"]["per_100g"]
    assert atta["energy_kcal"] == round(1340 / 4.184)
    assert atta["iron_mg"] == pytest.approx(4.1)
    assert atta["calcium_mg"] == pytest.approx(30.94)
    assert ifct_foods["A019"]["quality_flags"] == []


def test_ifct_local_names(ifct_foods):
    assert ifct_foods["A019"]["local_names"] == ["Wheat", "Atta", "Godhumai maavu"]


def test_ifct_comma_separated_local_names():
    assert ifct.parse_local_names("E. Mung bean, Maash, Moong; H. Mung dal.") == ["Mung bean", "Maash", "Moong", "Mung dal"]


def test_ifct_zero_energy_fat_recomputed(ifct_foods):
    ghee = ifct_foods["T013"]
    assert ghee["per_100g"]["energy_kcal"] == 884
    assert "energy_recomputed_from_macros" in ghee["quality_flags"]
    assert ghee["density_g_per_ml"] == 0.92


def test_ifct_transcription_error_corrected(ifct_foods):
    leg = ifct_foods["N001"]
    assert leg["per_100g"]["energy_kcal"] == 191
    assert "energy_corrected_from_macros" in leg["quality_flags"]


INDB_HEADER = ["food_code", "food_name", "primarysource", "energy_kcal", "protein_g", "carb_g", "fat_g", "fibre_g",
               "servings_unit", "unit_serving_energy_kcal", "unit_serving_protein_g", "unit_serving_carb_g",
               "unit_serving_fat_g", "unit_serving_fibre_g"]
RECIPE_HEADER = ["recipe_code", "ingredient_name_org", "unit_org", "food_code", "food_name", "amount", "unit"]
SERVING_HEADER = ["recipe_code", "no_of_servings", "size_of_servings", "servings_unit"]


def build(nutrient_rows, recipe_rows, serving_rows):
    dishes = indb.build([INDB_HEADER, *nutrient_rows], [RECIPE_HEADER, *recipe_rows], [SERVING_HEADER, *serving_rows])
    return {d["source_code"]: d for d in dishes}


def test_indb_added_fat_per_unit_serving():
    d = build(
        [["ASC096", "Chapati/Roti", "asc", 202, 6, 40, 2, 3, "chapati", 73, 2.2, 14, 2.0, 1]],
        [["ASC096", "Whole wheat flour", "g", "A019", "Wheat flour", 80, "g"],
         ["ASC096", "Ghee or butter", "tsp", "T506", "Ghee, butter", 1, "tsp"]],
        [["ASC096", 1, 4, "chapati"]],
    )["ASC096"]
    assert d["serving"]["added_fat_g"] == pytest.approx(5 * 0.92 / 4, abs=0.01)
    assert d["serving"]["container_ml"] is None
    assert not d["quarantined"]


def test_indb_bowl_is_container():
    d = build(
        [["ASC171", "Potato cauliflower (Aloo gobhi)", "asc", 106, 2, 8, 7, 2, "bowl", 187, 3.6, 14, 14.5, 3]],
        [["ASC171", "Fat", "tbsp", "T508", "Oil, sunflower", 1, "tbsp"]],
        [["ASC171", 1, 1, "bowl"]],
    )["ASC171"]
    assert d["serving"]["container_ml"] == 150.0
    assert d["local_names"] == ["Aloo gobhi"]
    assert d["serving"]["added_fat_g"] == pytest.approx(13.8)


def test_indb_deep_frying_oil_quarantined():
    d = build(
        [["ASC118", "Paneer pulao", "asc", 400, 10, 50, 50, 1, "plate", 4876, 30, 120, 501, 3]],
        [["ASC118", "Fat", "C", "T508", "Oil, sunflower", 2, "C"]],
        [["ASC118", 1, 1, "plate"]],
    )["ASC118"]
    assert d["quarantined"]
    assert "deep_frying_oil_counted" in d["quality_flags"]


def test_indb_missing_core_values_quarantined():
    d = build(
        [["X1", "Mystery dish", "osr", 100, 1, 1, 1, 1, "bowl", None, None, None, None, None]],
        [],
        [["X1", 1, 1, "bowl"]],
    )["X1"]
    assert d["quarantined"]
    assert "missing_core_values" in d["quality_flags"]


def test_derived_dish_swaps_one_ingredient():
    from app.importers import curated
    from app.nutrition import nutrients as N

    def ing(fid, code, kcal, protein):
        return {"_id": fid, "source_code": code, "name": code, "per_100g": {**N.zero(), "energy_kcal": kcal, "protein_g": protein}}

    base = {"_id": "indb:ASC151", "name": "Washed moong dal", "quarantined": False, "diet": "veg", "jain_ok": True,
            "ingredients": [{"name": "Green gram, dal", "code": "B010", "amount": 30, "unit": "g"}],
            "serving": {"unit": "bowl", "container_ml": 150.0, "added_fat_g": 4.6,
                        "nutrients": {**N.zero(), "energy_kcal": 139.0, "protein_g": 7.4}}}
    by_id = {d["_id"]: d for d in [base, ing("ifct:B010", "B010", 330.0, 24.0), ing("ifct:B021", "B021", 335.0, 21.7)]}
    dish = curated._derive(curated.DERIVED_DISHES[0], by_id)
    assert dish["serving"]["nutrients"]["energy_kcal"] == round(139 + 0.3 * (335 - 330))
    assert dish["serving"]["nutrients"]["protein_g"] == pytest.approx(7.4 + 0.3 * (21.7 - 24.0))
    assert dish["serving"]["added_fat_g"] == 4.6
    assert dish["ingredients"][0]["code"] == "B021"


@pytest.mark.parametrize(
    ("name", "ingredients", "expected"),
    [
        ("Chicken curry", [{"code": "D075", "name": "Tomato"}], ("nonveg", False)),
        ("Paneer potato cutlet", [{"code": "M001", "name": "Egg, poultry, whole, raw"}], ("egg", False)),
        ("Mayonnaise without eggs", [{"code": "T508", "name": "Oil, sunflower"}], ("veg", True)),
        ("Aloo gobhi", [{"code": "F006", "name": "Potato"}, {"code": "D036", "name": "Cauliflower"}], ("veg", False)),
        ("Dal tadka", [{"code": "B021", "name": "Red gram, dal"}, {"code": "G017", "name": "Onion, big"}], ("veg", False)),
        ("Plain dosa", [{"code": "A015", "name": "Rice"}, {"code": "B003", "name": "Black gram, dal"}], ("veg", True)),
        ("Prawn masala", [{"code": "UK-1", "name": "Prawns, raw"}], ("nonveg", False)),
    ],
)
def test_dish_diet_classification(name, ingredients, expected):
    from app.nutrition.diet import classify_dish

    assert classify_dish(name, ingredients) == expected


def test_brand_foods_load_with_sources():
    from app.importers import brands

    docs = {d["_id"]: d for d in brands.load()}
    slice_ = docs["brand:pizza_hut:margherita-pizza-personal-pan-4-slices-per-pizza"]
    assert slice_["serving"]["unit"] == "slice"
    # Pizza Hut India lists 725.1 kcal for the 4-slice personal pan Margherita.
    assert slice_["serving"]["nutrients"]["energy_kcal"] == round(725.1 / 4)
    assert "pizzahut.co.in" in slice_["source_note"]
    assert "partial_nutrients" in slice_["quality_flags"]

    fries = docs["brand:mcdonalds:fries-regular"]
    assert fries["serving"]["nutrients"]["energy_kcal"] == round(215.77)
    assert "carbs_by_difference" in fries["quality_flags"]  # McDonald's doesn't publish carbs for fries

    wing = docs["brand:kfc:hot-wings"]
    assert wing["serving"]["unit"] == "piece" and wing["diet"] == "nonveg"
    assert wing["serving"]["nutrients"]["energy_kcal"] == round(267.1 / 2)

    thums_up = docs["brand:packaged_drinks:thums-up"]
    assert thums_up["kind"] == "ingredient" and thums_up["per_100g"]["energy_kcal"] == 42


def test_every_brand_food_passes_energy_check():
    from app.importers import brands
    from scripts.extract_brand_pdfs import energy_ok

    for d in brands.load():
        values = d["serving"]["nutrients"] if d["kind"] == "dish" else d["per_100g"]
        assert energy_ok(values), d["name"]


@pytest.mark.parametrize(
    ("a", "b"),
    [("aloo", "aaloo"), ("aloo", "alu"), ("gobhi", "gobi"), ("paneer", "panir"), ("parantha", "paratha"),
     ("idli", "idly"), ("chicken", "chiken"), ("biryani", "biriyani"), ("sabzi", "sabji"), ("chhole", "chole"), ("dal", "daal")],
)
def test_spelling_variants_share_a_key(a, b):
    from app.search_text import key

    assert key(a) == key(b)
