from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import GoogleVerifier, clear_session, google_verifier, set_session
from app.config import Settings, get_settings
from app.db import get_db
from app.models import GoogleLogin, UserOut
from app.nutrition.measures import UserMeasures
from app.routers.me import user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=UserOut)
async def google_login(
    body: GoogleLogin,
    response: Response,
    verify: GoogleVerifier = Depends(google_verifier),
    settings: Settings = Depends(get_settings),
    db: AsyncDatabase = Depends(get_db),
):
    claims = verify(body.credential)
    now = datetime.now(UTC)
    user = await db.users.find_one_and_update(
        {"google_sub": claims["sub"]},
        {
            "$set": {
                "email": claims["email"],
                "name": claims.get("name") or claims["email"],
                "picture": claims.get("picture"),
                "last_login_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "measures": UserMeasures().model_dump(),
                "targets_custom": False,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    set_session(response, str(user["_id"]), settings)
    return user_out(user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    clear_session(response)
