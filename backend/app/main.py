"""
FastAPI server: the HTTP front door for the React page.

Search, match and skill-gap endpoints call the tools directly, so they work
with NO API key. Only /api/chat needs the LLM.
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()  # reads backend/.env (OPENAI_API_KEY, LLM_MODEL, DATABASE_URL)

from app import tools  # noqa: E402
from app.agent import build_agent, run_agent  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.skills import extract_skills  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create the table on startup if it is missing
    yield


app = FastAPI(title="InternInsider", lifespan=lifespan)

# DEMO ONLY: allow any website to call this API. In production, list the real frontend URL.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_agent = None  # built on the first chat request, then reused


class ResumeRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=20000)


class SkillGapRequest(ResumeRequest):
    job_id: int


class TextRequest(BaseModel):
    text: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    resume_text: str = Field(default="", max_length=20000)
    history: list[dict] = []  # [{"role": "user" | "assistant", "content": "..."}]


def llm_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_MODEL"))


@app.get("/api/health")
def health():
    with connect() as conn:
        count = conn.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"]
    return {"jobs": count, "llm_configured": llm_configured()}


@app.get("/api/jobs")
def list_jobs():
    """All postings, for the Jobs page before the user has searched."""
    with connect() as conn:
        return conn.execute(
            "SELECT id, title, company, location, category, skills FROM jobs ORDER BY id LIMIT 60"
        ).fetchall()


@app.post("/api/skills")
def skills(body: TextRequest):
    """Skills found in a piece of text (used to show what the resume contains)."""
    return extract_skills(body.text)


@app.get("/api/jobs/search")
def search(q: str, limit: int = 5):
    return tools.search_jobs(q, limit)


@app.get("/api/jobs/{job_id}")
def job(job_id: int):
    result = tools.get_job(job_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/match")
def match(body: ResumeRequest):
    return tools.match_resume(body.resume_text)


@app.post("/api/skill-gap")
def gap(body: SkillGapRequest):
    result = tools.skill_gap(body.resume_text, body.job_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/chat")
def chat(body: ChatRequest):
    """Run the LangGraph agent for one user message."""
    global _agent
    if not llm_configured():
        raise HTTPException(503, "No LLM key. Put OPENAI_API_KEY=... in backend/.env and restart the backend.")
    try:
        if _agent is None:
            _agent = build_agent()
        return run_agent(_agent, body.message, body.resume_text, body.history)
    except Exception as error:  # bad key, no credit, network down...
        raise HTTPException(502, f"The LLM call failed: {error}")
