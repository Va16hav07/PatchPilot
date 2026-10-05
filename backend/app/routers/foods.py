from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo.asynchronous.database import AsyncDatabase

from app import food_access
from app.auth import current_user
from app.db import get_db
from app.models import FoodDetail, FoodSummary, Portion, PortionOut
from app.nutrition.engine import PortionError, compute_portion, units_for
from app.nutrition.measures import UserMeasures

router = APIRouter(prefix="/api/foods", tags=["foods"])


def base_nutrients(food: dict) -> tuple[str, dict]:
    if food["kind"] == "ingredient":
        return "100 g", food["per_100g"]
    return f"1 {food['serving']['unit']}", food["serving"]["nutrients"]


def summary(food: dict) -> FoodSummary:
    basis, values = base_nutrients(food)
    return FoodSummary(
        id=food["_id"],
        name=food["name"],
        source=food["source"],
        kind=food["kind"],
        local_names=food.get("local_names", []),
        basis=basis,
        energy_kcal=values["energy_kcal"],
        protein_g=values["protein_g"],
        units=units_for(food),
    )


@router.get("", response_model=list[FoodSummary])
async def search_foods(
    q: str = Query(min_length=1, max_length=60),
    kind: Literal["ingredient", "dish"] | None = None,
    limit: int = Query(25, ge=1, le=50),
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
):
    return [summary(f) for f in await food_access.search(db, user, q, kind, limit)]


class CandidateQuery(BaseModel):
    terms: list[str] = Field(min_length=1, max_length=6)


class CandidatesIn(BaseModel):
    items: list[CandidateQuery] = Field(min_length=1, max_length=20)
    per_item: int = Field(8, ge=1, le=15)


@router.post("/candidates", response_model=list[list[FoodSummary]])
async def candidates(body: CandidatesIn, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    """Database matches for each AI-parsed item. The AI may only choose among these."""
    out = []
    for item in body.items:
        seen: dict[str, dict] = {}
        for term in item.terms:
            for f in await food_access.search(db, user, term[:60], limit=body.per_item):
                seen.setdefault(f["_id"], f)
        # Order by best rank under any of the item's terms.
        ranked = sorted(seen.values(), key=lambda f: min(food_access.rank(f, t.strip().lower()) for t in item.terms))
        out.append([summary(f) for f in ranked[: body.per_item]])
    return out


@router.get("/{food_id}", response_model=FoodDetail)
async def get_food(food_id: str, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    food = await food_access.get_visible_food(db, user, food_id)
    _, values = base_nutrients(food)
    serving = food.get("serving") or {}
    return FoodDetail(
        **summary(food).model_dump(),
        nutrients=values,
        group=food.get("group"),
        serving_unit=serving.get("unit"),
        added_fat_g=serving.get("added_fat_g"),
        ingredients=food.get("ingredients"),
        derived_from=food.get("recipe_source") if food.get("derived_from") else None,
        quality_flags=food.get("quality_flags", []),
    )


@router.post("/{food_id}/portion", response_model=PortionOut)
async def preview_portion(
    food_id: str, portion: Portion, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)
):
    """Nutrients for a portion, without logging it (live confirm screen)."""
    food = await food_access.get_visible_food(db, user, food_id)
    try:
        r = compute_portion(food, portion.quantity, portion.unit, UserMeasures(**user.get("measures", {})), portion.oil_level)
    except PortionError as exc:
        raise HTTPException(422, str(exc)) from exc
    return PortionOut(nutrients=r.nutrients, grams=r.grams, servings=r.servings, assumptions=r.assumptions)
