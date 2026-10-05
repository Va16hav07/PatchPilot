"""Meal logging.

Each entry stores a snapshot of the computed nutrients, so a later database
correction never silently rewrites what you ate last week.
"""

import datetime as dt
from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import current_user
from app.db import get_db
from app.food_access import get_loggable_food
from app.models import MEALS, CopyMeal, DayOut, DaySummary, LogBatch, LogCreate, LogEntryOut, Portion, RecentFood
from app.nutrition import nutrients as N
from app.nutrition.engine import PortionError, compute_portion
from app.nutrition.measures import UserMeasures

router = APIRouter(prefix="/api", tags=["logs"])


def entry_out(e: dict) -> LogEntryOut:
    return LogEntryOut(id=str(e["_id"]), **{k: v for k, v in e.items() if k not in ("_id", "user_id", "created_at")})


def _compute(food: dict, portion: Portion, user: dict) -> dict:
    try:
        r = compute_portion(food, portion.quantity, portion.unit, UserMeasures(**user.get("measures", {})), portion.oil_level)
    except PortionError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "quantity": portion.quantity,
        "unit": portion.unit,
        "oil_level": portion.oil_level,
        "grams": round(r.grams, 1) if r.grams is not None else None,
        "servings": round(r.servings, 3) if r.servings is not None else None,
        "nutrients": N.rounded(r.nutrients),
        "assumptions": r.assumptions,
    }


def _oid(entry_id: str) -> ObjectId:
    try:
        return ObjectId(entry_id)
    except InvalidId as exc:
        raise HTTPException(404, "entry not found") from exc


def _new_entry(food: dict, portion: Portion, user: dict, date: dt.date, meal: str) -> dict:
    return {
        "user_id": user["_id"],
        "date": date.isoformat(),
        "meal": meal,
        "food_id": food["_id"],
        "food_name": food["name"],
        "source": food["source"],
        "serving_unit": (food.get("serving") or {}).get("unit"),
        **_compute(food, portion, user),
        "created_at": datetime.now(UTC),
    }


async def _insert(db: AsyncDatabase, docs: list[dict]) -> list[LogEntryOut]:
    result = await db.log_entries.insert_many(docs)
    for doc, oid in zip(docs, result.inserted_ids):
        doc["_id"] = oid
    return [entry_out(d) for d in docs]


@router.post("/logs", response_model=LogEntryOut, status_code=201)
async def create_entry(body: LogCreate, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    food = await get_loggable_food(db, user, body.food_id)
    return (await _insert(db, [_new_entry(food, body, user, body.date, body.meal)]))[0]


@router.post("/logs/batch", response_model=list[LogEntryOut], status_code=201)
async def create_entries(body: LogBatch, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    """Log several items at once (a reviewed AI-parsed meal). All or nothing."""
    docs = []
    for item in body.items:
        food = await get_loggable_food(db, user, item.food_id)
        docs.append(_new_entry(food, item, user, body.date, body.meal))
    return await _insert(db, docs)


@router.post("/days/{date}/copy", response_model=list[LogEntryOut], status_code=201)
async def copy_meal(
    date: dt.date, body: CopyMeal, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)
):
    """Copy a meal from another day ("same as yesterday"), recalculated with current data and measures."""
    source = await db.log_entries.find(
        {"user_id": user["_id"], "date": body.from_date.isoformat(), "meal": body.from_meal}
    ).sort("created_at", 1).to_list()
    if not source:
        raise HTTPException(404, "nothing logged for that meal")
    docs = []
    for e in source:
        food = await get_loggable_food(db, user, e["food_id"])
        portion = Portion(quantity=e["quantity"], unit=e["unit"], oil_level=e["oil_level"])
        docs.append(_new_entry(food, portion, user, date, body.to_meal))
    return await _insert(db, docs)


@router.get("/logs/recent", response_model=list[RecentFood])
async def recent_foods(
    limit: int = Query(8, ge=1, le=20), user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)
):
    """Most recently logged distinct foods, with the portion last used."""
    pipeline = [
        {"$match": {"user_id": user["_id"]}},
        {"$sort": {"created_at": -1}},
        {"$limit": 500},
        {"$group": {"_id": "$food_id", "last": {"$first": "$$ROOT"}}},
        {"$sort": {"last.created_at": -1}},
        {"$limit": limit},
    ]
    out = []
    async for row in await db.log_entries.aggregate(pipeline):
        e = row["last"]
        out.append(RecentFood(
            food_id=e["food_id"], food_name=e["food_name"], source=e["source"], quantity=e["quantity"],
            unit=e["unit"], serving_unit=e.get("serving_unit"), oil_level=e["oil_level"],
            energy_kcal=e["nutrients"]["energy_kcal"],
        ))
    return out


@router.patch("/logs/{entry_id}", response_model=LogEntryOut)
async def update_entry(
    entry_id: str, body: Portion, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)
):
    query = {"_id": _oid(entry_id), "user_id": user["_id"]}
    entry = await db.log_entries.find_one(query)
    if entry is None:
        raise HTTPException(404, "entry not found")
    food = await get_loggable_food(db, user, entry["food_id"])
    updated = await db.log_entries.find_one_and_update(
        query, {"$set": _compute(food, body, user)}, return_document=ReturnDocument.AFTER
    )
    return entry_out(updated)


@router.delete("/logs/{entry_id}", status_code=204)
async def delete_entry(entry_id: str, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    result = await db.log_entries.delete_one({"_id": _oid(entry_id), "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "entry not found")


@router.get("/days/{date}", response_model=DayOut)
async def get_day(date: dt.date, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    entries = await db.log_entries.find({"user_id": user["_id"], "date": date.isoformat()}).sort("created_at", 1).to_list()
    meals: dict[str, list[LogEntryOut]] = {m: [] for m in MEALS}
    totals = N.zero()
    for e in entries:
        meals[e["meal"]].append(entry_out(e))
        totals = N.add(totals, e["nutrients"])
    return DayOut(date=date, targets=user.get("targets"), totals=N.rounded(totals), meals=meals)


MAX_RANGE_DAYS = 92


@router.get("/days", response_model=list[DaySummary])
async def get_days(
    start: dt.date = Query(),
    end: dt.date = Query(),
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
):
    """Daily totals for every date in [start, end], including days with nothing logged."""
    if end < start or (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(422, f"range must be 1-{MAX_RANGE_DAYS} days")
    query = {"user_id": user["_id"], "date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    by_date: dict[str, list[dict]] = {}
    async for e in db.log_entries.find(query, {"date": 1, "nutrients": 1}):
        by_date.setdefault(e["date"], []).append(e["nutrients"])
    out = []
    for i in range((end - start).days + 1):
        day = start + dt.timedelta(days=i)
        items = by_date.get(day.isoformat(), [])
        totals = N.zero()
        for n in items:
            totals = N.add(totals, n)
        out.append(DaySummary(date=day, totals=N.rounded(totals), entries=len(items)))
    return out
