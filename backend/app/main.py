"""
FastAPI server: the HTTP front door for the React page.

Search, match, skill-gap and resume-upload endpoints call plain Python
functions, so they work with NO API key. Only /api/chat needs the LLM.
"""
import os
import shutil
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()  # reads backend/.env (OPENAI_API_KEY, LLM_MODEL, DATABASE_URL)

from app import tools  # noqa: E402
from app.agent import build_agent, run_agent  # noqa: E402
from app.db import connect, init_db, save_chat, save_resume  # noqa: E402
from app.resume_parser import parse_resume  # noqa: E402
from app.skills import extract_skills, group_skills  # noqa: E402

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


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
        counts = conn.execute(
            "SELECT count(*) AS jobs, count(*) FILTER (WHERE source = 'linkedin') AS linkedin FROM jobs"
        ).fetchone()
    return {**counts, "llm_configured": llm_configured(), "ocr_available": shutil.which("tesseract") is not None}


@app.get("/api/jobs")
def list_jobs():
    """All postings, newest first, for the Jobs page before the user has searched."""
    with connect() as conn:
        return conn.execute(
            f"SELECT {tools.LIST_COLUMNS} FROM jobs ORDER BY posted_at DESC NULLS LAST, id LIMIT 300"
        ).fetchall()


@app.post("/api/skills")
def skills(body: TextRequest):
    """Skills found in a piece of text, flat and grouped."""
    found = extract_skills(body.text)
    return {"skills": found, "groups": group_skills(found)}


@app.post("/api/resume/parse")
def parse_resume_file(file: UploadFile = File(...)):
    """Upload a resume (PDF, PNG, JPG). Returns its text, how it was read, and the skills found."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 10 MB.")
    try:
        result = parse_resume(data)
    except ValueError as error:  # not a PDF or image, or too many pages
        raise HTTPException(400, str(error))
    if not result["text"].strip():
        raise HTTPException(422, "No text found in that file.")
    found = extract_skills(result["text"])
    resume_id = save_resume(file.filename, result, found)  # keep a record in PostgreSQL
    return {**result, "id": resume_id, "filename": file.filename, "skills": found, "groups": group_skills(found)}


@app.get("/api/history")
def history():
    """What has been saved: the latest uploads, and the latest copilot answers with their token counts."""
    with connect() as conn:
        resumes = conn.execute(
            "SELECT id, filename, method, pages, ocr_confidence, cardinality(skills) AS skills_found, created_at "
            "FROM resumes ORDER BY id DESC LIMIT 20"
        ).fetchall()
        chats = conn.execute(
            "SELECT id, question, tools_used, prompt_tokens, completion_tokens, created_at "
            "FROM chats ORDER BY id DESC LIMIT 20"
        ).fetchall()
    return {"resumes": resumes, "chats": chats}


@app.get("/api/jobs/search")
def search(q: str, limit: int = 5):
    return tools.search_jobs(q, min(limit, 50))


@app.get("/api/jobs/{job_id}")
def job(job_id: int):
    result = tools.get_job(job_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/match")
def match(body: ResumeRequest):
    return tools.match_resume(body.resume_text, limit=10)


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
        result = run_agent(_agent, body.message, body.resume_text, body.history)
    except Exception as error:  # bad key, no credit, network down...
        raise HTTPException(502, f"The LLM call failed: {error}")
    save_chat(body.message, result)  # keep a record in PostgreSQL, with the token count
    return result
