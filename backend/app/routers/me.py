from fastapi import APIRouter, Depends
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.auth import current_user
from app.db import get_db
from app.models import UserOut
from app.nutrition.measures import UserMeasures
from app.nutrition.targets import Profile, Targets, compute_targets

router = APIRouter(prefix="/api/me", tags=["me"])


def user_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user["name"],
        picture=user.get("picture"),
        profile=user.get("profile"),
        targets=user.get("targets"),
        targets_custom=user.get("targets_custom", False),
        measures=user.get("measures") or UserMeasures(),
    )


async def _update(db: AsyncDatabase, user: dict, fields: dict) -> UserOut:
    updated = await db.users.find_one_and_update(
        {"_id": user["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER
    )
    return user_out(updated)


@router.get("", response_model=UserOut)
async def get_me(user: dict = Depends(current_user)):
    return user_out(user)


@router.put("/profile", response_model=UserOut)
async def put_profile(profile: Profile, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    """Saving the profile recalculates targets from ICMR-NIN 2020."""
    targets = compute_targets(profile)
    return await _update(
        db, user, {"profile": profile.model_dump(), "targets": targets.model_dump(), "targets_custom": False}
    )


@router.put("/targets", response_model=UserOut)
async def put_targets(targets: Targets, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    return await _update(db, user, {"targets": targets.model_dump(), "targets_custom": True})


@router.post("/targets/preview", response_model=Targets)
async def preview_targets(profile: Profile, user: dict = Depends(current_user)):
    """Targets for a profile, without saving (live preview during setup)."""
    return compute_targets(profile)


@router.put("/measures", response_model=UserOut)
async def put_measures(measures: UserMeasures, user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db)):
    return await _update(db, user, {"measures": measures.model_dump()})
