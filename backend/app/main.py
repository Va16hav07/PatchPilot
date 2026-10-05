from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import get_settings
from app.routers import ai, auth, foods, logs, me, recipes


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = db.connect(settings.mongo_uri, settings.mongo_db)
    await db.ensure_indexes(database)
    yield
    await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Thali", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (auth.router, me.router, foods.router, logs.router, recipes.router, ai.router):
        app.include_router(r)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    return app


app = create_app()
