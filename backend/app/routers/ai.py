"""Gemini relay, used only when the user has no Gemini key on their device.

The frontend builds the whole Gemini request (prompt + JSON schema) and either
sends it straight to Google with the user's own key (which never reaches us),
or posts it here to go out with the server's key. This module forwards it,
restricted to allow-listed models and a per-user daily cap.
"""

import datetime as dt
import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import current_user
from app.config import Settings, get_settings
from app.db import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_REQUEST_BYTES = 6_000_000  # a compressed meal photo is well under this
TIMEOUT_S = 60.0


class AiStatus(BaseModel):
    server_key: bool
    models: list[str]
    daily_limit: int


class GenerateIn(BaseModel):
    model: str
    contents: list[dict[str, Any]] = Field(min_length=1, max_length=4)
    generationConfig: dict[str, Any] | None = None
    systemInstruction: dict[str, Any] | None = None


@router.get("/status", response_model=AiStatus)
async def status(user: dict = Depends(current_user), settings: Settings = Depends(get_settings)):
    return AiStatus(server_key=bool(settings.gemini_api_key), models=settings.gemini_models, daily_limit=settings.ai_daily_limit)


async def _count_call(db: AsyncDatabase, user: dict, limit: int) -> None:
    today = dt.date.today().isoformat()
    usage = await db.ai_usage.find_one_and_update(
        {"user_id": user["_id"], "date": today},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if usage["count"] > limit:
        raise HTTPException(429, "Daily AI limit reached on the shared key. Add your own Gemini key in Profile.")


@router.post("/generate")
async def generate(
    body: GenerateIn,
    user: dict = Depends(current_user),
    settings: Settings = Depends(get_settings),
    db: AsyncDatabase = Depends(get_db),
):
    if not settings.gemini_api_key:
        raise HTTPException(503, "No shared Gemini key on the server. Add your own Gemini key in Profile.")
    if body.model not in settings.gemini_models:
        raise HTTPException(422, f"model must be one of {settings.gemini_models}")
    payload = body.model_dump(exclude={"model"}, exclude_none=True)
    if len(json.dumps(payload)) > MAX_REQUEST_BYTES:
        raise HTTPException(413, "request too large")
    await _count_call(db, user, settings.ai_daily_limit)

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            res = await client.post(
                GEMINI_URL.format(model=body.model),
                json=payload,
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Could not reach Gemini") from exc
    if res.status_code != 200:
        # Don't leak Google's error body verbatim (it can echo request details).
        if res.status_code == 429:
            raise HTTPException(429, "The shared Gemini key is over its quota. Add your own key in Profile.")
        raise HTTPException(502, f"Gemini returned an error ({res.status_code})")
    return res.json()
