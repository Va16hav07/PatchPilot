"""Which foods a user can see, and food search.

Shared foods (IFCT, INDB, USDA) have no `owner_id`. A user's own recipes carry
`owner_id` and are visible only to that user.
"""

import re

from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase

SEARCH_POOL = 200
_PROJECTION = {"ingredients": 0, "per_100g_raw_basis": 0}


def visible(user: dict) -> dict:
    # {"$in": [None, id]} also matches documents without the field.
    return {"owner_id": {"$in": [None, user["_id"]]}}


async def get_visible_food(db: AsyncDatabase, user: dict, food_id: str) -> dict:
    food = await db.foods.find_one({"_id": food_id, **visible(user)})
    if food is None:
        raise HTTPException(404, "food not found")
    return food


async def get_loggable_food(db: AsyncDatabase, user: dict, food_id: str) -> dict:
    food = await get_visible_food(db, user, food_id)
    if food.get("quarantined"):
        raise HTTPException(422, "this food failed data-quality checks and can't be logged")
    return food


def _match_tier(name: str, q: str) -> int:
    """0 exact; 1/2 starts with / contains q as a whole word; 3/4 the same as part
    of a longer word ("dosa" in "Dosakaya"); 5 contains; 6 no match."""
    n = name.lower()
    if n == q:
        return 0
    word = rf"\b{re.escape(q)}\b"
    if re.match(word, n):
        return 1
    if re.search(word, n):
        return 2
    if n.startswith(q):
        return 3
    if re.search(rf"\b{re.escape(q)}", n):
        return 4
    return 5 if q in n else 6


def rank(food: dict, q: str) -> tuple:
    """A match on the food's own name beats a local-name match up to one tier better;
    then the user's own recipes, then dishes before ingredients, then shorter names."""
    name_tier = _match_tier(food["name"], q)
    local_tier = min((_match_tier(n, q) for n in food.get("local_names", [])), default=6)
    best = min(name_tier * 2, local_tier * 2 + 3)
    own = 0 if food.get("owner_id") else 1
    return (best, own, 0 if food["kind"] == "dish" else 1, len(food["name"]))


async def search(db: AsyncDatabase, user: dict, q: str, kind: str | None = None, limit: int = 25) -> list[dict]:
    term = q.strip().lower()
    if not term:
        return []
    pattern = {"$regex": re.escape(term), "$options": "i"}
    query: dict = {
        "quarantined": False,
        "$and": [visible(user), {"$or": [{"name": pattern}, {"local_names": pattern}]}],
    }
    if kind:
        query["kind"] = kind
    foods = await db.foods.find(query, _PROJECTION).limit(SEARCH_POOL).to_list()
    foods.sort(key=lambda f: rank(f, term))
    return foods[:limit]
