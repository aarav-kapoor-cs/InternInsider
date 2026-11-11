"""
Test setup. Tests use a separate database (interninsider_test) and the fake
embedder, so they need no model download, no network and no API key.
"""
import os

import psycopg
import pytest

BASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/interninsider")
SERVER_URL = BASE_URL.rsplit("/", 1)[0]

# Set these BEFORE the app is imported.
os.environ["DATABASE_URL"] = SERVER_URL + "/interninsider_test"
os.environ["EMBEDDINGS"] = "fake"
# Empty, not removed: load_dotenv() never overwrites a variable that is already set,
# so a real key in backend/.env cannot leak into the tests.
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""

from app.ingest import ingest, load_sample  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create the test database once and load the 24 sample postings."""
    with psycopg.connect(SERVER_URL + "/postgres", autocommit=True) as admin:
        if not admin.execute("SELECT 1 FROM pg_database WHERE datname = 'interninsider_test'").fetchone():
            admin.execute("CREATE DATABASE interninsider_test")
    ingest(load_sample())
