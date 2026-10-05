import pytest

from app.nutrition.targets import Profile, compute_targets


def energy(sex, weight, activity, age=25):
    return compute_targets(Profile(sex=sex, age=age, height_cm=165, weight_kg=weight, activity=activity)).energy_kcal


# ICMR-NIN 2020 reference adults (65 kg man, 55 kg woman).
@pytest.mark.parametrize(
    ("sex", "weight", "activity", "expected"),
    [
        ("male", 65, "sedentary", 2110),
        ("male", 65, "moderate", 2710),
        ("male", 65, "heavy", 3470),
        ("female", 55, "sedentary", 1660),
        ("female", 55, "moderate", 2130),
    ],
)
def test_energy_matches_icmr_reference(sex, weight, activity, expected):
    assert abs(energy(sex, weight, activity) - expected) <= 20


def test_protein_is_0_83_g_per_kg():
    t = compute_targets(Profile(sex="male", age=30, height_cm=172, weight_kg=71))
    assert t.protein_g == round(0.83 * 71)


def test_macros_add_up_to_energy():
    t = compute_targets(Profile(sex="female", age=40, height_cm=160, weight_kg=60, activity="moderate"))
    assert abs(t.protein_g * 4 + t.carb_g * 4 + t.fat_g * 9 - t.energy_kcal) < 15


def test_goal_changes_energy():
    base = dict(sex="male", age=30, height_cm=172, weight_kg=71)
    lose = compute_targets(Profile(**base, goal="lose")).energy_kcal
    keep = compute_targets(Profile(**base, goal="maintain")).energy_kcal
    gain = compute_targets(Profile(**base, goal="gain")).energy_kcal
    assert lose < keep < gain
