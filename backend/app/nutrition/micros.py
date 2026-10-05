"""Vitamin and mineral reference values.

RDA and EAR: ICMR-NIN 2020 "Nutrient Requirements for Indians", brief note,
Table 3 (men) and Table 4 (women). The RDA is the daily target; an average
intake below the EAR means intake is likely inadequate.

Limits (things to keep under) and potassium: WHO guidance, since the ICMR
brief note gives no figures for them.
"""

from dataclasses import dataclass
from typing import Literal

Sex = Literal["male", "female"]


@dataclass(frozen=True)
class Reference:
    key: str
    label: str
    unit: str
    rda: float
    ear: float | None


_RDA_EAR: dict[str, tuple[str, str, dict[str, tuple[float, float]]]] = {
    # key: (label, unit, {sex: (RDA, EAR)})
    "calcium_mg": ("Calcium", "mg", {"male": (1000, 800), "female": (1000, 800)}),
    "magnesium_mg": ("Magnesium", "mg", {"male": (440, 370), "female": (370, 310)}),
    "iron_mg": ("Iron", "mg", {"male": (19, 11), "female": (29, 15)}),
    "zinc_mg": ("Zinc", "mg", {"male": (17, 14), "female": (13, 11)}),
    "vit_b1_mg": ("Thiamine (B1)", "mg", {"male": (1.8, 1.5), "female": (1.7, 1.4)}),
    "vit_b2_mg": ("Riboflavin (B2)", "mg", {"male": (2.5, 2.1), "female": (2.4, 2.0)}),
    "vit_b3_mg": ("Niacin (B3)", "mg", {"male": (18, 15), "female": (14, 12)}),
    "vit_b6_mg": ("Vitamin B6", "mg", {"male": (2.4, 2.1), "female": (1.9, 1.6)}),
    "folate_ug": ("Folate", "µg", {"male": (300, 250), "female": (220, 180)}),
    "vit_c_mg": ("Vitamin C", "mg", {"male": (80, 65), "female": (65, 55)}),
}

POTASSIUM = Reference("potassium_mg", "Potassium", "mg", 3510, None)  # WHO 2012: at least 3510 mg/day

# Upper limits. Fixed amounts, or a share of daily energy (WHO).
SODIUM_LIMIT_MG = 2000.0  # WHO: under 2 g sodium (5 g salt) a day
SUGAR_ENERGY_SHARE = 0.10  # WHO: free sugars under 10% of energy
SAT_FAT_ENERGY_SHARE = 0.10  # WHO: saturated fat under 10% of energy


def references(sex: Sex) -> list[Reference]:
    refs = [Reference(k, label, unit, *by_sex[sex]) for k, (label, unit, by_sex) in _RDA_EAR.items()]
    return refs + [POTASSIUM]


@dataclass(frozen=True)
class Limit:
    key: str
    label: str
    unit: str
    limit: float


def limits(energy_kcal: float) -> list[Limit]:
    return [
        Limit("sodium_mg", "Sodium", "mg", SODIUM_LIMIT_MG),
        Limit("sugar_g", "Free sugars", "g", energy_kcal * SUGAR_ENERGY_SHARE / 4.0),
        Limit("sat_fat_g", "Saturated fat", "g", energy_kcal * SAT_FAT_ENERGY_SHARE / 9.0),
    ]


Status = Literal["good", "borderline", "low"]


def status(avg: float, ref: Reference) -> Status:
    if avg >= ref.rda:
        return "good"
    if ref.ear is not None and avg < ref.ear:
        return "low"
    if ref.ear is None and avg < 0.7 * ref.rda:
        return "low"
    return "borderline"
