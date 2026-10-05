from pymongo import ASCENDING, TEXT, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None


def connect(uri: str, name: str) -> AsyncDatabase:
    global _client, _db
    _client = AsyncMongoClient(uri, tz_aware=True)
    _db = _client[name]
    return _db


async def close() -> None:
    global _client, _db
    if _client is not None:
        await _client.close()
    _client, _db = None, None


def get_db() -> AsyncDatabase:
    if _db is None:
        raise RuntimeError("database not connected")
    return _db


async def ensure_indexes(db: AsyncDatabase) -> None:
    await db.users.create_index("google_sub", unique=True)
    await db.foods.create_index(
        [("name", TEXT), ("local_names", TEXT)],
        weights={"name": 10, "local_names": 5},
        default_language="none",
        name="food_text",
    )
    await db.foods.create_index([("quarantined", ASCENDING), ("kind", ASCENDING)])
    await db.log_entries.create_index([("user_id", ASCENDING), ("date", ASCENDING)])
    await db.log_entries.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    await db.foods.create_index("owner_id", sparse=True)
    await db.ai_usage.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
