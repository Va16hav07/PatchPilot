import pytest

from app.nutrition import nutrients as N
from app.nutrition.engine import PortionError, compute_portion, units_for
from app.nutrition.measures import UserMeasures


def per(**kw):
    return {**N.zero(), **kw}


ATTA = {"_id": "ifct:A019", "name": "Wheat flour, atta", "kind": "ingredient",
        "per_100g": per(energy_kcal=320.0, protein_g=10.57, fat_g=1.53), "density_g_per_ml": None}
OIL = {"_id": "ifct:T012", "name": "Sunflower oil", "kind": "ingredient",
       "per_100g": per(energy_kcal=884.0, fat_g=100.0), "density_g_per_ml": 0.92}
ALOO_GOBHI = {"_id": "indb:ASC171", "name": "Aloo gobhi", "kind": "dish",
              "serving": {"unit": "bowl", "container_ml": 150.0, "added_fat_g": 13.8,
                          "nutrients": per(energy_kcal=187.0, fat_g=14.5, protein_g=3.6)}}
ROTI = {"_id": "indb:ASC096", "name": "Chapati/Roti", "kind": "dish",
        "serving": {"unit": "chapati", "container_ml": None, "added_fat_g": 1.15,
                    "nutrients": per(energy_kcal=73.0, protein_g=2.2)}}


def test_ingredient_grams():
    r = compute_portion(ATTA, 50, "g")
    assert r.grams == 50
    assert r.nutrients["energy_kcal"] == pytest.approx(160.0)
    assert r.nutrients["protein_g"] == pytest.approx(5.285)


def test_ingredient_by_volume_uses_density():
    r = compute_portion(OIL, 1, "tbsp")
    assert r.grams == pytest.approx(15 * 0.92)
    assert r.nutrients["energy_kcal"] == pytest.approx(13.8 * 8.84)


def test_volume_units_only_for_pourable_foods():
    assert units_for(ATTA) == ["g"]
    with pytest.raises(PortionError):
        compute_portion(ATTA, 1, "katori")


def test_dish_servings():
    r = compute_portion(ROTI, 2, "serving")
    assert r.servings == 2
    assert r.grams is None
    assert r.nutrients["energy_kcal"] == pytest.approx(146.0)


def test_countable_dish_has_no_katori():
    assert units_for(ROTI) == ["serving"]
    with pytest.raises(PortionError):
        compute_portion(ROTI, 1, "katori")


def test_katori_scales_by_users_katori_and_states_assumption():
    r = compute_portion(ALOO_GOBHI, 1, "katori", UserMeasures(katori_ml=200))
    assert r.servings == pytest.approx(200 / 150)
    assert r.nutrients["energy_kcal"] == pytest.approx(187.0 * 200 / 150)
    assert any("150 ml" in a and "200 ml" in a for a in r.assumptions)


@pytest.mark.parametrize(("level", "delta_fat"), [("low", -6.9), ("home", 0.0), ("restaurant", 13.8)])
def test_oil_level_adjusts_only_added_fat(level, delta_fat):
    r = compute_portion(ALOO_GOBHI, 1, "serving", oil_level=level)
    assert r.nutrients["fat_g"] == pytest.approx(14.5 + delta_fat)
    assert r.nutrients["energy_kcal"] == pytest.approx(187.0 + delta_fat * 9)
    assert r.nutrients["protein_g"] == pytest.approx(3.6)


def test_oil_level_ignored_without_added_fat():
    dish = {**ALOO_GOBHI, "serving": {**ALOO_GOBHI["serving"], "added_fat_g": None}}
    r = compute_portion(dish, 1, "serving", oil_level="restaurant")
    assert r.nutrients["energy_kcal"] == pytest.approx(187.0)
    assert r.assumptions


@pytest.mark.parametrize("qty", [0, -1])
def test_rejects_non_positive_quantity(qty):
    with pytest.raises(PortionError):
        compute_portion(ATTA, qty, "g")
