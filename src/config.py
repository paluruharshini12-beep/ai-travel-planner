"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_path: Path
    openweather_api_key: str
    mapbox_access_token: str
    openai_api_key: str
    gemini_api_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str


def get_settings() -> Settings:
    """Read settings at runtime, allowing .env values to be changed without code edits."""
    db_value = os.getenv("DATABASE_PATH", "data/wanderly.db")
    db_path = Path(db_value)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    return Settings(
        database_path=db_path,
        openweather_api_key=os.getenv("OPENWEATHER_API_KEY", "").strip(),
        mapbox_access_token=os.getenv("MAPBOX_ACCESS_TOKEN", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        google_redirect_uri=os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8501"
        ).strip(),
    )
