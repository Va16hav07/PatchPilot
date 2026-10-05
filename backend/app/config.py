from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db: str = "thali"

    # OAuth client ID from Google Cloud Console (Web application type).
    google_client_id: str = ""

    # Signs session cookies. Must be a long random string in production.
    session_secret: str = "dev-only-insecure-secret-change-me-in-prod"
    session_days: int = 30
    cookie_secure: bool = False  # True when served over HTTPS

    cors_origins: list[str] = [
        "http://localhost:5173",
        "https://nutri-thali.vercel.app",
    ]

    # Optional shared Gemini key. Users can instead keep their own key on their
    # device; that key is never sent to this server.
    gemini_api_key: str = ""
    gemini_models: list[str] = ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
    ai_daily_limit: int = 150


@lru_cache
def get_settings() -> Settings:
    return Settings()
