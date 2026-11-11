"""
Database + embeddings. Everything that touches PostgreSQL or turns text into
a vector lives here.
"""
import hashlib
import math
import os
import re

import psycopg
from psycopg.rows import dict_row

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/interninsider"
EMBEDDING_DIM = 384  # size of the vectors produced by the embedding model below

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;          -- turns on pgvector

CREATE TABLE IF NOT EXISTS jobs (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',        -- frontend, backend, data, devops, mobile, security
    url         TEXT NOT NULL DEFAULT '',        -- the posting on LinkedIn
    logo_url    TEXT NOT NULL DEFAULT '',
    posted_at   DATE,
    source      TEXT NOT NULL DEFAULT 'sample',  -- 'linkedin' or 'sample'
    description TEXT NOT NULL,
    skills      TEXT[] NOT NULL DEFAULT '{{}}',   -- skills found in the posting
    embedding   vector({EMBEDDING_DIM}) NOT NULL  -- the meaning of the posting as {EMBEDDING_DIM} numbers
);

-- HNSW is an approximate nearest-neighbour index. Without it Postgres compares
-- the query against every row (fine for hundreds of jobs, slow for millions).
CREATE INDEX IF NOT EXISTS idx_jobs_embedding
    ON jobs USING hnsw (embedding vector_cosine_ops);

-- Every uploaded resume and how it was read.
CREATE TABLE IF NOT EXISTS resumes (
    id             SERIAL PRIMARY KEY,
    filename       TEXT NOT NULL,
    method         TEXT NOT NULL,                -- 'text', 'ocr' or 'mixed'
    pages          INT NOT NULL,
    ocr_confidence REAL,                         -- NULL when no OCR was needed
    seconds        REAL NOT NULL,
    text           TEXT NOT NULL,
    skills         TEXT[] NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every copilot answer: which tools the agent used and how many tokens it cost.
CREATE TABLE IF NOT EXISTS chats (
    id                SERIAL PRIMARY KEY,
    question          TEXT NOT NULL,
    answer            TEXT NOT NULL,
    tools_used        TEXT[] NOT NULL,
    prompt_tokens     INT NOT NULL,
    completion_tokens INT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect():
    """Open a connection. Rows come back as dicts, e.g. row["title"]."""
    return psycopg.connect(
        os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL), row_factory=dict_row
    )


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA_SQL)


def save_resume(filename: str, result: dict, skills: list[str]) -> int:
    """Store one uploaded resume and how it was read. Returns the new row's id."""
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO resumes (filename, method, pages, ocr_confidence, seconds, text, skills)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (filename, result["method"], result["pages"], result["ocr_confidence"],
             result["seconds"], result["text"], skills),
        ).fetchone()
    return row["id"]


def save_chat(question: str, result: dict) -> int:
    """Store one copilot answer with the tools it used and its token count. Returns the row's id."""
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO chats (question, answer, tools_used, prompt_tokens, completion_tokens)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (question, result["reply"], [call["name"] for call in result["tool_calls"]],
             result["tokens"]["prompt"], result["tokens"]["completion"]),
        ).fetchone()
    return row["id"]


# ------------------------------------------------------------- embeddings

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_model = None


def job_text(title: str, skills: list[str], description: str) -> str:
    """
    The text that gets embedded for one posting. The model only reads about the
    first 512 tokens, and LinkedIn descriptions often open with paragraphs about
    the company, so the title and the extracted skills go first.
    """
    skills_part = f"Skills: {', '.join(skills)}. " if skills else ""
    return f"{title}. {skills_part}{description}"


def embed(text: str) -> list[float]:
    """
    Turn text into a list of 384 numbers (an "embedding"). Texts with similar
    MEANING get vectors that point in similar directions, even when they share
    no words: "build user interfaces" lands near "React developer".

    The model (BAAI/bge-small-en-v1.5) runs locally through fastembed, so
    search needs no API key and costs nothing. The first call downloads it.
    """
    if os.environ.get("EMBEDDINGS") == "fake":
        return _fake_embed(text)
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(EMBEDDING_MODEL)
    return [float(x) for x in next(iter(_model.embed([text])))]


def _fake_embed(text: str) -> list[float]:
    """
    TEST ONLY (EMBEDDINGS=fake). No model, no download: each word is hashed
    into one of the 384 slots. It only matches shared words, not meaning, but
    it lets the tests exercise the real pgvector SQL quickly and offline.
    """
    vec = [0.0] * EMBEDDING_DIM
    for word in re.findall(r"[a-z0-9+#]+", text.lower()):
        slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM
        vec[slot] += 1.0
    length = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / length for x in vec]


def to_pgvector(vec: list[float]) -> str:
    """pgvector accepts a vector written as text: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
