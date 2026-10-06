"""Averages over a date range compared with ICMR-NIN 2020 references, plus
food suggestions for the biggest gaps, drawn from the food database.

Averages are over days that have anything logged, so days you skipped
logging don't count as days you ate nothing.
"""

import datetime as dt
import re
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import current_user
from app.db import get_db
from app.food_access import visible
from app.nutrition import micros
from app.nutrition import nutrients as N
from app.nutrition.diet import allowed_query
from app.nutrition.measures import UserMeasures

router = APIRouter(prefix="/api/insights", tags=["insights"])

MAX_RANGE_DAYS = 92
MIN_DAYS_FOR_TRENDS = 3
MAX_SUGGESTION_KCAL = 600  # don't suggest a portion that is a meal in itself
MAX_SUGGESTION_SODIUM_MG = 600  # nor a salty one (pickles, papads)
# INDB servings that are a whole batch or a condiment spoonful, not one person's portion.
NON_PORTION_UNITS = {
    "jar", "glass jar", "dish", "souffle dish", "casserole dish", "small casserole dish", "shallow dish",
    "pie", "flan", "cake", "small mould", "tablespoon", "teaspoon", "half-pints", "ml",
}
# Concentrated foods eaten in small amounts, whatever their group.
_SMALL_PORTION = re.compile(r"\b(dried|dry|dehydrated|tamarind|powder)\b", re.I)
SUGGESTIONS_PER_NUTRIENT = 4
MIN_SHARE = 0.15  # a suggested portion gives at least this share of the daily target
GAPS_SUGGESTED = 3

# Typical portion of raw ingredients, by IFCT group, so "100 g of cumin" never
# tops an iron list. Groups not listed (spices, oils, sugars, misc) are not suggested.
GROUP_PORTION: dict[str, tuple[float, str]] = {
    "Green Leafy Vegetables": (100, "100 g"),
    "Other Vegetables": (100, "100 g"),
    "Roots and Tubers": (100, "100 g"),
    "Fruits": (100, "100 g"),
    "Mushrooms": (100, "100 g"),
    "Grain Legumes": (30, "30 g dry (about 1 katori cooked)"),
    "Cereals and Millets": (50, "50 g flour or grain"),
    "Nuts and Oil Seeds": (30, "30 g (a small handful)"),
    "Egg and Egg Products": (50, "1 egg"),
    "Poultry": (100, "100 g"),
    "Animal Meat": (100, "100 g"),
    "Marine Fish": (100, "100 g"),
    "Fresh Water Fish and Shellfish": (100, "100 g"),
    "Marine Shellfish": (100, "100 g"),
    "Marine Mollusks": (100, "100 g"),
}
CODE_PORTION: dict[str, tuple[float, str]] = {
    "L001": (200, "1 glass (200 ml)"),
    "L002": (200, "1 glass (200 ml)"),
    "L003": (50, "50 g"),
    "L004": (30, "30 g"),
    "171284": (150, "1 katori"),  # USDA curd
}


class NutrientAvg(BaseModel):
    key: str
    label: str
    unit: str
    avg: float
    target: float
    pct: float


class MicroOut(NutrientAvg):
    ear: float | None
    status: micros.Status


class LimitOut(BaseModel):
    key: str
    label: str
    unit: str
    avg: float
    limit: float
    over: bool


class SuggestedFood(BaseModel):
    id: str
    name: str
    source: str
    portion: str
    amount: float
    pct_of_target: float
    energy_kcal: float
    you_eat_it: bool


class Suggestion(BaseModel):
    key: str
    label: str
    unit: str
    gap: float
    foods: list[SuggestedFood]


class InsightsOut(BaseModel):
    start: dt.date
    end: dt.date
    days_logged: int
    enough_data: bool
    diet: str | None
    energy: NutrientAvg | None
    macros: list[NutrientAvg]
    micros: list[MicroOut]
    limits: list[LimitOut]
    suggestions: list[Suggestion]


def _portion(food: dict, measures: UserMeasures) -> tuple[float, str, dict] | None:
    """(factor applied to the food's base values, label, base values) for a typical portion."""
    if food["kind"] == "dish":
        unit = food["serving"]["unit"]
        if unit.lower() in NON_PORTION_UNITS:
            return None
        return 1.0, f"1 {unit}", food["serving"]["nutrients"]
    if food.get("owner_id"):  # user's own recipe: a katori
        grams = measures.katori_ml * (food.get("density_g_per_ml") or 1.0)
        return grams / 100, "1 katori", food["per_100g"]
    by_code = CODE_PORTION.get(food.get("source_code") or "")
    grams_label = by_code or GROUP_PORTION.get(food.get("group") or "")
    if not grams_label:
        return None
    grams, label = grams_label
    if _SMALL_PORTION.search(food["name"]):
        grams, label = 10, "10 g"
    return grams / 100, label, food["per_100g"]


def _family(name: str) -> str:
    """'Brinjal 14' and 'Brinjal - all varieties' are one suggestion, not twenty."""
    head = re.split(r"[,(-]", name)[0]
    return re.sub(r"\d+", "", head).strip().lower()


async def _suggest(db, user: dict, keys_targets: list[tuple[str, str, str, float, float]], eaten: set[str]) -> list[Suggestion]:
    if not keys_targets:
        return []
    # Unknown diet: suggest vegetarian food only, which suits everyone.
    diet = (user.get("profile") or {}).get("diet") or "vegetarian"
    # Brand fast food publishes only partial nutrients, and is not what we suggest.
    query = {"quarantined": False, "quality_flags": {"$ne": "partial_nutrients"}, **visible(user), **allowed_query(diet)}
    projection = {"name": 1, "kind": 1, "group": 1, "source": 1, "source_code": 1, "owner_id": 1,
                  "per_100g": 1, "serving": 1, "density_g_per_ml": 1}
    foods = await db.foods.find(query, projection).to_list()
    measures = UserMeasures(**user.get("measures", {}))

    portions = []
    for f in foods:
        p = _portion(f, measures)
        if p is None:
            continue
        factor, label, base = p
        kcal = base.get("energy_kcal", 0) * factor
        sodium = base.get("sodium_mg", 0) * factor
        if 0 < kcal <= MAX_SUGGESTION_KCAL and sodium <= MAX_SUGGESTION_SODIUM_MG:
            portions.append((f, factor, label, base, kcal))

    out = []
    for key, label, unit, gap, target in keys_targets:
        # A portion must make a real dent (MIN_SHARE of the target); among those,
        # the most nutrient per calorie wins, so big heavy dishes don't win by size.
        scored = [
            (base.get(key, 0) * factor, f, label_, kcal)
            for f, factor, label_, base, kcal in portions
            if base.get(key, 0) * factor >= MIN_SHARE * target
        ]
        if not scored:
            continue
        best_density = max(a / k for a, _, _, k in scored)
        # Foods you already eat first, if they are at least half as dense as the best option.
        scored.sort(key=lambda t: (not (t[1]["_id"] in eaten and t[0] / t[3] >= best_density / 2), -t[0] / t[3]))
        picked, families = [], set()
        for amount, f, portion_label, kcal in scored:
            fam = _family(f["name"])
            if fam in families:
                continue
            families.add(fam)
            picked.append(SuggestedFood(
                id=f["_id"], name=f["name"], source=f["source"], portion=portion_label,
                amount=round(amount, 2), pct_of_target=round(amount / target * 100), energy_kcal=round(kcal),
                you_eat_it=f["_id"] in eaten,
            ))
            if len(picked) == SUGGESTIONS_PER_NUTRIENT:
                break
        out.append(Suggestion(key=key, label=label, unit=unit, gap=round(gap, 2), foods=picked))
    return out


def _avg(key: str, label: str, unit: str, avg: float, target: float) -> NutrientAvg:
    return NutrientAvg(key=key, label=label, unit=unit, avg=round(avg, 2), target=target,
                       pct=round(avg / target * 100) if target else 0)


@router.get("", response_model=InsightsOut)
async def insights(
    start: dt.date = Query(),
    end: dt.date = Query(),
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
):
    if end < start or (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(422, f"range must be 1-{MAX_RANGE_DAYS} days")
    profile = user.get("profile")
    if not profile:
        raise HTTPException(409, "set up your profile first")

    by_day: dict[str, dict[str, float]] = defaultdict(N.zero)
    eaten: set[str] = set()
    query = {"user_id": user["_id"], "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    async for e in db.log_entries.find(query, {"date": 1, "nutrients": 1, "food_id": 1}):
        by_day[e["date"]] = N.add(by_day[e["date"]], e["nutrients"])
        eaten.add(e["food_id"])
    days = len(by_day)
    totals = N.zero()
    for day_totals in by_day.values():
        totals = N.add(totals, day_totals)
    avg = N.scale(totals, 1 / days) if days else N.zero()

    targets = user.get("targets") or {}
    energy = _avg("energy_kcal", "Energy", "kcal", avg["energy_kcal"], targets["energy_kcal"]) if targets else None
    macro_defs = [("protein_g", "Protein"), ("carb_g", "Carbs"), ("fat_g", "Fat"), ("fibre_g", "Fibre")]
    macros = [_avg(k, label, "g", avg[k], targets[k]) for k, label in macro_defs if targets.get(k)]

    micro_out = []
    for ref in micros.references(profile["sex"]):
        a = avg[ref.key]
        micro_out.append(MicroOut(key=ref.key, label=ref.label, unit=ref.unit, avg=round(a, 2), target=ref.rda,
                                  pct=round(a / ref.rda * 100), ear=ref.ear, status=micros.status(a, ref)))

    limit_out = [
        LimitOut(key=lim.key, label=lim.label, unit=lim.unit, avg=round(avg[lim.key], 2), limit=round(lim.limit, 1),
                 over=avg[lim.key] > lim.limit)
        for lim in micros.limits(targets.get("energy_kcal") or 2000)
    ]

    gaps: list[tuple[str, str, str, float, float]] = []
    if days:
        for m in [m for m in macros if m.key in ("protein_g", "fibre_g") and m.pct < 80]:
            gaps.append((m.key, m.label, m.unit, m.target - m.avg, m.target))
        lows = sorted((m for m in micro_out if m.status == "low"), key=lambda m: m.pct)
        for m in lows[:GAPS_SUGGESTED]:
            gaps.append((m.key, m.label, m.unit, m.target - m.avg, m.target))

    return InsightsOut(
        start=start, end=end, days_logged=days, enough_data=days >= MIN_DAYS_FOR_TRENDS,
        diet=profile.get("diet"), energy=energy, macros=macros, micros=micro_out, limits=limit_out,
        suggestions=await _suggest(db, user, gaps, eaten),
    )
