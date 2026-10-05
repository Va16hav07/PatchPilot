"""The user's own recipes ("Mom's rajma").

A recipe is raw ingredients (weighed) plus the cooked weight of the whole pot.
Nutrients per 100 g cooked = sum of ingredient nutrients / cooked weight, which
is exact for what's in the pot, unlike INDB's raw-weight basis. It's stored as
a private food, so search, portions and logging all work unchanged.
"""

from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import current_user
from app.db import get_db
from app.food_access import get_visible_food
from app.nutrition import nutrients as N

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

SOURCE = "MY_RECIPE"
# Cooked dishes poured into a katori: water-like density. An assumption, shown to the user.
COOKED_DENSITY_G_PER_ML = 1.0


class Ingredient(BaseModel):
    food_id: str
    grams: float = Field(gt=0, le=20000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ingredients: list[Ingredient] = Field(min_length=1, max_length=40)
    cooked_weight_g: float = Field(gt=0, le=50000)


class RecipeIngredientOut(BaseModel):
    food_id: str
    name: str
    grams: float


class RecipeOut(BaseModel):
    id: str
    name: str
    ingredients: list[RecipeIngredientOut]
    raw_weight_g: float
    cooked_weight_g: float
    per_100g: dict[str, float]


class RecipePreview(BaseModel):
    raw_weight_g: float
    per_100g: dict[str, float]


DIET_RANK = {"veg": 0, "egg": 1, "nonveg": 2}


async def _compute(db: AsyncDatabase, user: dict, body: RecipeIn) -> tuple[list[dict], float, dict, dict]:
    total = N.zero()
    rows = []
    diet, jain_ok = "veg", True
    for ing in body.ingredients:
        food = await get_visible_food(db, user, ing.food_id)
        if food["kind"] != "ingredient":
            raise HTTPException(422, f"'{food['name']}' is a cooked dish; add raw ingredients by weight")
        if food.get("quarantined"):
            raise HTTPException(422, f"'{food['name']}' failed data-quality checks")
        total = N.add(total, N.scale(food["per_100g"], ing.grams / 100.0))
        food_diet = food.get("diet", "veg")
        if DIET_RANK[food_diet] > DIET_RANK[diet]:
            diet = food_diet
        jain_ok = jain_ok and food.get("jain_ok", False)
        rows.append({"food_id": food["_id"], "name": food["name"], "grams": ing.grams})
    raw_weight = sum(r["grams"] for r in rows)
    per_100g = N.rounded(N.scale(total, 100.0 / body.cooked_weight_g))
    return rows, raw_weight, per_100g, {"diet": diet, "jain_ok": jain_ok and diet == "veg"}


def _out(doc: dict) -> RecipeOut:
    r = doc["recipe"]
    return RecipeOut(
        id=doc["_id"],
        name=doc["name"],
        ingredients=r["ingredients"],
        raw_weight_g=r["raw_weight_g"],
        cooked_weight_g=r["cooked_weight_g"],
        per_100g=doc["per_100g"],
    )


async def _own(db: AsyncDatabase, user: dict, recipe_id: str) -> dict:
    doc = await db.foods.find_one({"_id": recipe_id, "owner_id": user["_id"], "source": SOURCE})
    if doc is None:
        raise HTTPException(404, "recipe not found")
    return doc


@router.post("/preview", response_model=RecipePreview)
async def preview(body: RecipeIn, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    _, raw, per_100g, _diet = await _compute(db, user, body)
    return RecipePreview(raw_weight_g=raw, per_100g=per_100g)


@router.get("", response_model=list[RecipeOut])
async def list_recipes(user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    docs = await db.foods.find({"owner_id": user["_id"], "source": SOURCE}).sort("name", 1).to_list()
    return [_out(d) for d in docs]


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(recipe_id: str, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    return _out(await _own(db, user, recipe_id))


def _doc_fields(body: RecipeIn, rows: list[dict], raw: float, per_100g: dict, diet: dict) -> dict:
    return {
        **diet,
        "name": body.name.strip(),
        "per_100g": per_100g,
        "recipe": {"ingredients": rows, "raw_weight_g": raw, "cooked_weight_g": body.cooked_weight_g},
        "updated_at": datetime.now(UTC),
    }


@router.post("", response_model=RecipeOut, status_code=201)
async def create_recipe(body: RecipeIn, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    rows, raw, per_100g, diet = await _compute(db, user, body)
    doc = {
        "_id": f"recipe:{ObjectId()}",
        "source": SOURCE,
        "source_code": None,
        "kind": "ingredient",
        "owner_id": user["_id"],
        "local_names": [],
        "group": "My recipes",
        "diet_tags": [],
        "density_g_per_ml": COOKED_DENSITY_G_PER_ML,
        "density_assumed": True,
        "quality_flags": [],
        "quarantined": False,
        "created_at": datetime.now(UTC),
        **_doc_fields(body, rows, raw, per_100g, diet),
    }
    await db.foods.insert_one(doc)
    return _out(doc)


@router.put("/{recipe_id}", response_model=RecipeOut)
async def update_recipe(
    recipe_id: str, body: RecipeIn, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)
):
    await _own(db, user, recipe_id)
    rows, raw, per_100g, diet = await _compute(db, user, body)
    fields = _doc_fields(body, rows, raw, per_100g, diet)
    await db.foods.update_one({"_id": recipe_id, "owner_id": user["_id"]}, {"$set": fields})
    return _out(await _own(db, user, recipe_id))


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(recipe_id: str, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    """Past log entries keep their nutrient snapshot."""
    await _own(db, user, recipe_id)
    await db.foods.delete_one({"_id": recipe_id, "owner_id": user["_id"]})
