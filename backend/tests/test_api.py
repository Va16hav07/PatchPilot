"""End-to-end API tests against a real MongoDB (database `thali_test`)."""

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from app import db as dbmod
from app.auth import google_verifier
from app.config import get_settings
from app.main import create_app
from app.nutrition import nutrients as N


def _mongo_available() -> bool:
    try:
        MongoClient(get_settings().mongo_uri, serverSelectionTimeoutMS=500).admin.command("ping")
        return True
    except ServerSelectionTimeoutError:
        return False


pytestmark = pytest.mark.skipif(not _mongo_available(), reason="MongoDB not running")

FOODS = [
    {"_id": "indb:ASC171", "source": "INDB", "source_code": "ASC171", "kind": "dish",
     "name": "Potato cauliflower (Aloo gobhi)", "local_names": ["Aloo gobhi"], "quarantined": False, "quality_flags": [],
     "serving": {"unit": "bowl", "container_ml": 150.0, "added_fat_g": 13.8,
                 "nutrients": {**N.zero(), "energy_kcal": 187.0, "protein_g": 3.6, "fat_g": 14.5}}},
    {"_id": "ifct:L003", "source": "IFCT2017", "source_code": "L003", "kind": "ingredient", "name": "Paneer",
     "local_names": [], "quarantined": False, "quality_flags": [], "density_g_per_ml": None,
     "per_100g": {**N.zero(), "energy_kcal": 258.0, "protein_g": 18.86}},
    {"_id": "indb:ASC118", "source": "INDB", "source_code": "ASC118", "kind": "dish", "name": "Paneer pulao",
     "local_names": [], "quarantined": True, "quality_flags": ["deep_frying_oil_counted"],
     "serving": {"unit": "plate", "container_ml": None, "added_fat_g": None,
                 "nutrients": {**N.zero(), "energy_kcal": 4876.0}}},
]


def fake_verifier():
    def verify(credential: str) -> dict:
        if not credential.startswith("good:"):
            raise HTTPException(401, "invalid Google credential")
        sub = credential.removeprefix("good:")
        return {"sub": sub, "email": f"{sub}@example.com", "name": sub.title(), "email_verified": True}

    return verify


@pytest_asyncio.fixture
async def app():
    settings = get_settings()
    database = dbmod.connect(settings.mongo_uri, settings.mongo_db)
    for name in ("users", "foods", "log_entries"):
        await database[name].drop()
    await dbmod.ensure_indexes(database)
    await database.foods.insert_many(FOODS)
    application = create_app()
    application.dependency_overrides[google_verifier] = fake_verifier
    yield application
    await dbmod.close()


async def client_for(app, user: str | None = "rohan") -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    if user:
        r = await client.post("/api/auth/google", json={"credential": f"good:{user}"})
        assert r.status_code == 200, r.text
    return client


async def test_requires_login(app):
    c = await client_for(app, user=None)
    assert (await c.get("/api/me")).status_code == 401
    assert (await c.get("/api/foods", params={"q": "aloo"})).status_code == 401
    assert (await c.post("/api/auth/google", json={"credential": "forged"})).status_code == 401


async def test_profile_sets_icmr_targets(app):
    c = await client_for(app)
    me = (await c.get("/api/me")).json()
    assert me["email"] == "rohan@example.com" and me["targets"] is None
    r = await c.put("/api/me/profile", json={"sex": "male", "age": 25, "height_cm": 170, "weight_kg": 65, "activity": "moderate"})
    assert r.status_code == 200
    assert abs(r.json()["targets"]["energy_kcal"] - 2710) <= 20


async def test_search_hides_quarantined_and_matches_local_names(app):
    c = await client_for(app)
    names = [f["name"] for f in (await c.get("/api/foods", params={"q": "paneer"})).json()]
    assert names == ["Paneer"]
    hit = (await c.get("/api/foods", params={"q": "aloo gob"})).json()
    assert hit[0]["id"] == "indb:ASC171"
    assert hit[0]["units"] == ["serving", "katori"]


async def test_log_and_day_totals(app):
    c = await client_for(app)
    await c.put("/api/me/measures", json={"katori_ml": 200, "glass_ml": 250})
    r = await c.post("/api/logs", json={"date": "2026-10-05", "meal": "lunch", "food_id": "indb:ASC171",
                                         "quantity": 1, "unit": "katori", "oil_level": "restaurant"})
    assert r.status_code == 201, r.text
    entry = r.json()
    servings = 200 / 150
    expected = (187.0 + 13.8 * 9) * servings
    assert entry["nutrients"]["energy_kcal"] == round(expected)
    assert entry["assumptions"]
    await c.post("/api/logs", json={"date": "2026-10-05", "meal": "dinner", "food_id": "ifct:L003", "quantity": 100, "unit": "g"})

    day = (await c.get("/api/days/2026-10-05")).json()
    assert len(day["meals"]["lunch"]) == 1 and len(day["meals"]["dinner"]) == 1
    assert day["totals"]["energy_kcal"] == pytest.approx(expected + 258, abs=1)


async def test_cannot_log_quarantined_food(app):
    c = await client_for(app)
    r = await c.post("/api/logs", json={"date": "2026-10-05", "meal": "lunch", "food_id": "indb:ASC118", "quantity": 1, "unit": "serving"})
    assert r.status_code == 422


async def test_invalid_unit_rejected(app):
    c = await client_for(app)
    r = await c.post("/api/foods/ifct:L003/portion", json={"quantity": 1, "unit": "katori"})
    assert r.status_code == 422


async def test_users_cannot_touch_each_others_entries(app):
    a = await client_for(app, "rohan")
    entry = (await a.post("/api/logs", json={"date": "2026-10-05", "meal": "lunch", "food_id": "ifct:L003", "quantity": 50, "unit": "g"})).json()
    b = await client_for(app, "intruder")
    assert (await b.delete(f"/api/logs/{entry['id']}")).status_code == 404
    assert (await b.patch(f"/api/logs/{entry['id']}", json={"quantity": 1, "unit": "g"})).status_code == 404
    assert (await b.get("/api/days/2026-10-05")).json()["totals"]["energy_kcal"] == 0
    assert (await a.delete(f"/api/logs/{entry['id']}")).status_code == 204


async def test_day_range_summary(app):
    c = await client_for(app)
    await c.post("/api/logs", json={"date": "2026-10-04", "meal": "lunch", "food_id": "ifct:L003", "quantity": 100, "unit": "g"})
    days = (await c.get("/api/days", params={"start": "2026-10-03", "end": "2026-10-05"})).json()
    assert [d["date"] for d in days] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert [d["entries"] for d in days] == [0, 1, 0]
    assert days[1]["totals"]["energy_kcal"] == 258
    assert (await c.get("/api/days", params={"start": "2026-10-05", "end": "2026-10-01"})).status_code == 422


# ---- Phase 2 -------------------------------------------------------------

ATTA = {"_id": "ifct:A019", "source": "IFCT2017", "source_code": "A019", "kind": "ingredient", "name": "Wheat flour, atta",
        "local_names": ["Atta"], "quarantined": False, "quality_flags": [], "density_g_per_ml": None,
        "per_100g": {**N.zero(), "energy_kcal": 320.0, "protein_g": 10.0, "fat_g": 1.5}}
OIL = {"_id": "ifct:T012", "source": "IFCT2017", "source_code": "T012", "kind": "ingredient", "name": "Sunflower oil",
       "local_names": [], "quarantined": False, "quality_flags": [], "density_g_per_ml": 0.92,
       "per_100g": {**N.zero(), "energy_kcal": 884.0, "fat_g": 100.0}}


async def _add_staples():
    await dbmod.get_db().foods.insert_many([ATTA, OIL])


async def test_recipe_per_100g_from_cooked_weight(app):
    await _add_staples()
    c = await client_for(app)
    body = {"name": "My parathas", "cooked_weight_g": 250,
            "ingredients": [{"food_id": "ifct:A019", "grams": 200}, {"food_id": "ifct:T012", "grams": 20}]}
    r = await c.post("/api/recipes", json=body)
    assert r.status_code == 201, r.text
    recipe = r.json()
    # (200 g atta * 3.2 + 20 g oil * 8.84) / 250 g cooked * 100
    assert recipe["per_100g"]["energy_kcal"] == round((640 + 176.8) / 250 * 100)
    assert recipe["raw_weight_g"] == 220

    hits = (await c.get("/api/foods", params={"q": "parathas"})).json()
    assert hits[0]["id"] == recipe["id"] and hits[0]["source"] == "MY_RECIPE"
    portion = (await c.post(f"/api/foods/{recipe['id']}/portion", json={"quantity": 1, "unit": "katori"})).json()
    assert portion["grams"] == 150 and portion["assumptions"]


async def test_recipe_rejects_cooked_dish_ingredient(app):
    c = await client_for(app)
    r = await c.post("/api/recipes", json={"name": "x", "cooked_weight_g": 100, "ingredients": [{"food_id": "indb:ASC171", "grams": 50}]})
    assert r.status_code == 422


async def test_recipes_are_private(app):
    await _add_staples()
    owner = await client_for(app, "rohan")
    recipe = (await owner.post("/api/recipes", json={"name": "Secret dal", "cooked_weight_g": 100,
                                                      "ingredients": [{"food_id": "ifct:A019", "grams": 50}]})).json()
    other = await client_for(app, "intruder")
    assert (await other.get("/api/foods", params={"q": "secret"})).json() == []
    assert (await other.get(f"/api/foods/{recipe['id']}")).status_code == 404
    assert (await other.get(f"/api/recipes/{recipe['id']}")).status_code == 404
    assert (await other.delete(f"/api/recipes/{recipe['id']}")).status_code == 404
    r = await other.post("/api/logs", json={"date": "2026-10-05", "meal": "lunch", "food_id": recipe["id"], "quantity": 100, "unit": "g"})
    assert r.status_code == 404
    assert (await owner.delete(f"/api/recipes/{recipe['id']}")).status_code == 204


async def test_candidates_per_item(app):
    c = await client_for(app)
    r = await c.post("/api/foods/candidates", json={"items": [{"terms": ["aloo gobhi", "potato cauliflower"]}, {"terms": ["paneer"]}, {"terms": ["xyzzy"]}]})
    assert r.status_code == 200
    out = r.json()
    assert out[0][0]["id"] == "indb:ASC171"
    assert [f["id"] for f in out[1]] == ["ifct:L003"]  # quarantined paneer pulao excluded
    assert out[2] == []


async def test_batch_is_all_or_nothing(app):
    c = await client_for(app)
    good = {"food_id": "ifct:L003", "quantity": 50, "unit": "g"}
    bad = {"food_id": "indb:ASC118", "quantity": 1, "unit": "serving"}  # quarantined
    assert (await c.post("/api/logs/batch", json={"date": "2026-10-05", "meal": "lunch", "items": [good, bad]})).status_code == 422
    assert (await c.get("/api/days/2026-10-05")).json()["totals"]["energy_kcal"] == 0
    r = await c.post("/api/logs/batch", json={"date": "2026-10-05", "meal": "lunch", "items": [good, {**good, "quantity": 100}]})
    assert r.status_code == 201 and len(r.json()) == 2


async def test_copy_meal_and_recent(app):
    c = await client_for(app)
    await c.post("/api/logs", json={"date": "2026-10-04", "meal": "lunch", "food_id": "indb:ASC171", "quantity": 1, "unit": "serving", "oil_level": "low"})
    await c.post("/api/logs", json={"date": "2026-10-04", "meal": "lunch", "food_id": "ifct:L003", "quantity": 80, "unit": "g"})
    r = await c.post("/api/days/2026-10-05/copy", json={"from_date": "2026-10-04", "from_meal": "lunch", "to_meal": "dinner"})
    assert r.status_code == 201
    day = (await c.get("/api/days/2026-10-05")).json()
    assert [e["food_id"] for e in day["meals"]["dinner"]] == ["indb:ASC171", "ifct:L003"]
    assert day["meals"]["dinner"][0]["oil_level"] == "low"
    assert (await c.post("/api/days/2026-10-05/copy", json={"from_date": "2026-10-01", "from_meal": "lunch", "to_meal": "lunch"})).status_code == 404

    recent = (await c.get("/api/logs/recent")).json()
    assert {f["food_id"] for f in recent} == {"indb:ASC171", "ifct:L003"}
    assert len(recent) == 2


async def test_ai_relay_without_server_key(app):
    c = await client_for(app)
    assert (await c.get("/api/ai/status")).json()["server_key"] is False
    r = await c.post("/api/ai/generate", json={"model": "gemini-3.6-flash", "contents": [{"parts": [{"text": "hi"}]}]})
    assert r.status_code == 503


async def test_ai_relay_forwards_with_server_key(app, monkeypatch):
    from app.config import Settings, get_settings as real

    def with_key() -> Settings:
        return real().model_copy(update={"gemini_api_key": "server-key", "ai_daily_limit": 2})

    app.dependency_overrides[get_settings] = with_key
    sent = {}

    class FakeGemini:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            sent.update(url=url, json=json, headers=headers)
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    from app.routers import ai as ai_router

    c = await client_for(app)  # real test client, created before patching
    monkeypatch.setattr(ai_router.httpx, "AsyncClient", FakeGemini)
    body = {"model": "gemini-3.6-flash", "contents": [{"parts": [{"text": "2 roti"}]}], "generationConfig": {"responseMimeType": "application/json"}}
    r = await c.post("/api/ai/generate", json=body)
    assert r.status_code == 200, r.text
    assert sent["url"].endswith("/models/gemini-3.6-flash:generateContent")
    assert sent["headers"]["x-goog-api-key"] == "server-key"
    assert "model" not in sent["json"]
    assert (await c.post("/api/ai/generate", json={**body, "model": "some-other-model"})).status_code == 422
    assert (await c.post("/api/ai/generate", json=body)).status_code == 200
    assert (await c.post("/api/ai/generate", json=body)).status_code == 429  # daily limit 2


# ---- Phase 3 -------------------------------------------------------------

SPINACH = {"_id": "ifct:C033", "source": "IFCT2017", "source_code": "C033", "kind": "ingredient", "name": "Spinach",
           "group": "Green Leafy Vegetables", "local_names": ["Palak"], "quarantined": False, "quality_flags": [],
           "density_g_per_ml": None, "diet": "veg", "jain_ok": True,
           "per_100g": {**N.zero(), "energy_kcal": 24.0, "iron_mg": 5.0, "calcium_mg": 90.0}}
LIVER = {"_id": "ifct:O020", "source": "IFCT2017", "source_code": "O020", "kind": "ingredient", "name": "Goat, liver",
         "group": "Animal Meat", "local_names": [], "quarantined": False, "quality_flags": [],
         "density_g_per_ml": None, "diet": "nonveg", "jain_ok": False,
         "per_100g": {**N.zero(), "energy_kcal": 120.0, "iron_mg": 9.0}}
CUMIN = {"_id": "ifct:G025", "source": "IFCT2017", "source_code": "G025", "kind": "ingredient", "name": "Cumin seeds",
         "group": "Condiments and Spices", "local_names": ["Jeera"], "quarantined": False, "quality_flags": [],
         "density_g_per_ml": None, "diet": "veg", "jain_ok": True,
         "per_100g": {**N.zero(), "energy_kcal": 370.0, "iron_mg": 66.0}}


async def _insights_user(app, diet):
    c = await client_for(app)
    await c.put("/api/me/profile", json={"sex": "female", "age": 30, "height_cm": 160, "weight_kg": 55, "diet": diet})
    return c


async def test_insights_averages_over_logged_days_only(app):
    c = await _insights_user(app, "vegetarian")
    await c.post("/api/logs", json={"date": "2026-10-01", "meal": "lunch", "food_id": "ifct:L003", "quantity": 100, "unit": "g"})
    await c.post("/api/logs", json={"date": "2026-10-03", "meal": "lunch", "food_id": "ifct:L003", "quantity": 300, "unit": "g"})
    r = (await c.get("/api/insights", params={"start": "2026-09-29", "end": "2026-10-05"})).json()
    assert r["days_logged"] == 2 and r["enough_data"] is False
    assert r["energy"]["avg"] == pytest.approx(258 * 2)  # (258 + 774) / 2 logged days, not / 7


async def test_insights_icmr_references_by_sex(app):
    c = await _insights_user(app, "vegetarian")
    await c.post("/api/logs", json={"date": "2026-10-01", "meal": "lunch", "food_id": "ifct:L003", "quantity": 100, "unit": "g"})
    r = (await c.get("/api/insights", params={"start": "2026-10-01", "end": "2026-10-01"})).json()
    iron = next(m for m in r["micros"] if m["key"] == "iron_mg")
    assert (iron["target"], iron["ear"], iron["status"]) == (29, 15, "low")  # ICMR 2020, women
    assert {lim["key"] for lim in r["limits"]} == {"sodium_mg", "sugar_g", "sat_fat_g"}


async def test_suggestions_respect_diet_and_skip_spices(app):
    await dbmod.get_db().foods.insert_many([SPINACH, LIVER, CUMIN])
    c = await _insights_user(app, "vegetarian")
    await c.post("/api/logs", json={"date": "2026-10-01", "meal": "lunch", "food_id": "ifct:L003", "quantity": 50, "unit": "g"})
    r = (await c.get("/api/insights", params={"start": "2026-10-01", "end": "2026-10-01"})).json()
    iron = next(s for s in r["suggestions"] if s["key"] == "iron_mg")
    ids = [f["id"] for f in iron["foods"]]
    assert ids[0] == "ifct:C033"
    assert "ifct:O020" not in ids  # non-veg hidden for a vegetarian
    assert "ifct:G025" not in ids  # spices aren't eaten by the 100 g
    assert iron["foods"][0]["portion"] == "100 g" and iron["foods"][0]["amount"] == 5.0

    await c.put("/api/me/profile", json={"sex": "female", "age": 30, "height_cm": 160, "weight_kg": 55, "diet": "non_vegetarian"})
    r = (await c.get("/api/insights", params={"start": "2026-10-01", "end": "2026-10-01"})).json()
    iron = next(s for s in r["suggestions"] if s["key"] == "iron_mg")
    assert [f["id"] for f in iron["foods"]] == ["ifct:C033", "ifct:O020"]  # ranked by iron per kcal


async def test_insights_needs_profile(app):
    c = await client_for(app)
    assert (await c.get("/api/insights", params={"start": "2026-10-01", "end": "2026-10-02"})).status_code == 409
