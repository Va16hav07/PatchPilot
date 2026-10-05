"""Deterministic nutrition engine: food + portion -> nutrients.

No AI here. Every number comes from the food document (IFCT / INDB data)
and the user's household measures. Anything that is an assumption rather
than data is returned in `assumptions` so the UI can show it.

Two kinds of food:
- "ingredient" (IFCT): values per 100 g. Portions resolve to grams.
- "dish" (INDB): values per standard serving. INDB's per-100 g values are on a
  raw-ingredient-weight basis (water and evaporation not accounted for), so
  grams of a cooked dish cannot be converted reliably. Portions resolve to a
  number of servings instead.
"""

from dataclasses import dataclass, field
from typing import Literal

from . import nutrients as N
from .measures import CONTAINER_SERVING_ML, UserMeasures, volume_ml

OilLevel = Literal["low", "home", "restaurant"]

# Multiplier on a recipe's added fat (oil / ghee / butter in the ingredient list).
OIL_MULTIPLIER: dict[str, float] = {"low": 0.5, "home": 1.0, "restaurant": 2.0}


class PortionError(ValueError):
    pass


@dataclass
class PortionResult:
    nutrients: dict[str, float]
    grams: float | None = None  # ingredients only
    servings: float | None = None  # dishes only
    assumptions: list[str] = field(default_factory=list)


def units_for(food: dict) -> list[str]:
    """Units a user may log this food in."""
    if food["kind"] == "ingredient":
        units = ["g"]
        if food.get("density_g_per_ml"):
            units += ["tsp", "tbsp", "katori", "cup", "glass", "ml"]
        return units
    serving = food["serving"]
    units = ["serving"]
    if serving.get("container_ml"):
        units.append("katori")
    return units


def compute_portion(
    food: dict,
    quantity: float,
    unit: str,
    measures: UserMeasures | None = None,
    oil_level: OilLevel = "home",
) -> PortionResult:
    if quantity <= 0:
        raise PortionError("quantity must be positive")
    measures = measures or UserMeasures()
    if unit not in units_for(food):
        raise PortionError(f"unit '{unit}' is not available for {food['name']}")
    if food["kind"] == "ingredient":
        return _ingredient(food, quantity, unit, measures)
    return _dish(food, quantity, unit, measures, oil_level)


def _ingredient(food: dict, quantity: float, unit: str, measures: UserMeasures) -> PortionResult:
    assumptions: list[str] = []
    if unit == "g":
        grams = quantity
    else:
        ml = quantity * volume_ml(unit, measures)
        grams = ml * food["density_g_per_ml"]
        if food.get("density_assumed"):
            assumptions.append(
                f"{ml:g} ml assumed to weigh {grams:g} g; weigh your portion and log grams for best accuracy"
            )
    values = N.scale(food["per_100g"], grams / 100.0)
    return PortionResult(nutrients=values, grams=grams, assumptions=assumptions)


def _dish(
    food: dict, quantity: float, unit: str, measures: UserMeasures, oil_level: OilLevel
) -> PortionResult:
    serving = food["serving"]
    assumptions: list[str] = []
    if unit == "serving":
        servings = quantity
    else:  # katori
        container_ml = serving["container_ml"]
        servings = quantity * measures.katori_ml / container_ml
        assumptions.append(
            f"1 standard {serving['unit']} assumed to be {container_ml:g} ml; "
            f"your katori is {measures.katori_ml:g} ml"
        )

    values = N.scale(serving["nutrients"], servings)

    if oil_level not in OIL_MULTIPLIER:
        raise PortionError(f"unknown oil level '{oil_level}'")
    added_fat = serving.get("added_fat_g") or 0.0
    if oil_level != "home":
        if added_fat <= 0:
            assumptions.append("This recipe has no added oil or ghee; oil level ignored")
        else:
            delta = added_fat * servings * (OIL_MULTIPLIER[oil_level] - 1.0)
            values["fat_g"] += delta
            values["energy_kcal"] += delta * N.FAT_KCAL_PER_G
            assumptions.append(
                f"Recipe uses {added_fat:.1f} g oil/ghee per serving; "
                f"adjusted ×{OIL_MULTIPLIER[oil_level]:g} for {oil_level} cooking"
            )
    return PortionResult(nutrients=values, servings=servings, assumptions=assumptions)


def container_ml_for(serving_unit: str | None) -> float | None:
    if not serving_unit:
        return None
    return CONTAINER_SERVING_ML.get(serving_unit.strip().lower())
