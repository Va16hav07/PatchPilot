"""Daily targets following ICMR-NIN 2020 "Nutrient Requirements for Indians".

Energy: BMR from the FAO/WHO/UNU 2004 weight-based equations, reduced by 10%
(men) / 9% (women) as ICMR-NIN 2020 does for Indians, times a physical
activity level (PAL). Checked against ICMR-NIN reference values: 65 kg man
-> 2110 / 2710 / 3470 kcal, 55 kg woman -> 1660 / 2130 kcal.
"""

from typing import Literal

from pydantic import BaseModel, Field

Sex = Literal["male", "female"]
Activity = Literal["sedentary", "moderate", "heavy"]
Goal = Literal["lose", "maintain", "gain"]

PAL: dict[str, float] = {"sedentary": 1.4, "moderate": 1.8, "heavy": 2.3}
INDIAN_BMR_FACTOR: dict[str, float] = {"male": 0.90, "female": 0.91}
GOAL_FACTOR: dict[str, float] = {"lose": 0.85, "maintain": 1.0, "gain": 1.10}

PROTEIN_G_PER_KG = 0.83  # ICMR-NIN 2020 RDA, adults
FAT_ENERGY_SHARE = 0.25
FIBRE_G_PER_1000_KCAL = 20.0  # ICMR-NIN 2020: 40 g per 2000 kcal


class Profile(BaseModel):
    sex: Sex
    age: int = Field(ge=18, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=250)
    activity: Activity = "moderate"
    goal: Goal = "maintain"


class Targets(BaseModel):
    energy_kcal: int
    protein_g: int
    carb_g: int
    fat_g: int
    fibre_g: int


def bmr_kcal(sex: Sex, age: int, weight_kg: float) -> float:
    """FAO/WHO/UNU 2004 (Schofield) BMR, adjusted for Indians."""
    if sex == "male":
        if age < 30:
            bmr = 15.057 * weight_kg + 692.2
        elif age < 60:
            bmr = 11.472 * weight_kg + 873.1
        else:
            bmr = 11.711 * weight_kg + 587.7
    else:
        if age < 30:
            bmr = 14.818 * weight_kg + 486.6
        elif age < 60:
            bmr = 8.126 * weight_kg + 845.6
        else:
            bmr = 9.082 * weight_kg + 658.5
    return bmr * INDIAN_BMR_FACTOR[sex]


def compute_targets(p: Profile) -> Targets:
    energy = bmr_kcal(p.sex, p.age, p.weight_kg) * PAL[p.activity] * GOAL_FACTOR[p.goal]
    protein = PROTEIN_G_PER_KG * p.weight_kg
    fat = energy * FAT_ENERGY_SHARE / 9.0
    carb = max(energy - protein * 4.0 - fat * 9.0, 0.0) / 4.0
    fibre = energy / 1000.0 * FIBRE_G_PER_1000_KCAL
    return Targets(
        energy_kcal=round(energy / 10) * 10,
        protein_g=round(protein),
        carb_g=round(carb),
        fat_g=round(fat),
        fibre_g=round(fibre),
    )
