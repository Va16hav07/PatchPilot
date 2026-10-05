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

    base = {"_id": "indb:ASC151", "name": "Washed moong dal", "quarantined": False,
            "ingredients": [{"name": "Green gram, dal", "code": "B010", "amount": 30, "unit": "g"}],
            "serving": {"unit": "bowl", "container_ml": 150.0, "added_fat_g": 4.6,
                        "nutrients": {**N.zero(), "energy_kcal": 139.0, "protein_g": 7.4}}}
    by_id = {d["_id"]: d for d in [base, ing("ifct:B010", "B010", 330.0, 24.0), ing("ifct:B021", "B021", 335.0, 21.7)]}
    dish = curated._derive(curated.DERIVED_DISHES[0], by_id)
    assert dish["serving"]["nutrients"]["energy_kcal"] == round(139 + 0.3 * (335 - 330))
    assert dish["serving"]["nutrients"]["protein_g"] == pytest.approx(7.4 + 0.3 * (21.7 - 24.0))
    assert dish["serving"]["added_fat_g"] == 4.6
    assert dish["ingredients"][0]["code"] == "B021"
