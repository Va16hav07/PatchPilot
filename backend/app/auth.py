"""Google sign-in (the only login method) and cookie sessions.

The frontend gets a Google ID token from Google Identity Services and posts it
to /api/auth/google. We verify it with Google's public keys, upsert the user,
and set an httpOnly session cookie holding a short signed JWT.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from bson import ObjectId
from fastapi import Cookie, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings, get_settings
from app.db import get_db

COOKIE = "session"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

GoogleVerifier = Callable[[str], dict]


def google_verifier(settings: Settings = Depends(get_settings)) -> GoogleVerifier:
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GOOGLE_CLIENT_ID is not configured")

    def verify(credential: str) -> dict:
        try:
            claims = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Google credential") from exc
        if claims.get("iss") not in GOOGLE_ISSUERS or not claims.get("email_verified"):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unverified Google account")
        return claims

    return verify


def set_session(response: Response, user_id: str, settings: Settings) -> None:
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    token = jwt.encode({"sub": user_id, "exp": expires}, settings.session_secret, algorithm="HS256")
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


async def current_user(
    session: str | None = Cookie(default=None),
    settings: Settings = Depends(get_settings),
    db: AsyncDatabase = Depends(get_db),
) -> dict:
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    try:
        claims = jwt.decode(session, settings.session_secret, algorithms=["HS256"])
        user_id = ObjectId(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
    user = await db.users.find_one({"_id": user_id})
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
