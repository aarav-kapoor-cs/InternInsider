"""
The 5 tools. Each one is a plain Python function with type hints and a
docstring. The SAME functions are used in three places:
  - the LangGraph agent   (agent.py)      the LLM decides when to call them
  - the MCP server        (mcp_server.py) other AI apps can call them
  - the REST API          (main.py)       the React page calls some directly
The docstrings matter: they are what the LLM reads to decide which tool to use.
"""
from app.db import connect, embed, to_pgvector
from app.skills import extract_skills


def search_jobs(query: str, limit: int = 5) -> list[dict]:
    """Search job postings by meaning. Use for requests like 'find backend internships'
    or 'jobs working with data'. Returns the closest postings with a similarity score (0 to 1)."""
    vector = to_pgvector(embed(query))
    with connect() as conn:
        # <=> is pgvector's cosine DISTANCE operator (0 = same direction).
        # Similarity is 1 - distance. ORDER BY distance = nearest first.
        rows = conn.execute(
            """
            SELECT id, title, company, location, skills,
                   round((1 - (embedding <=> %s::vector))::numeric, 3)::float AS similarity
            FROM jobs
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, vector, limit),
        ).fetchall()
    return rows


def get_job(job_id: int) -> dict:
    """Get the full details of one job posting, including its description, by its id."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, title, company, location, category, url, description, skills FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
    return row or {"error": f"No job with id {job_id}"}


def match_resume(resume_text: str, limit: int = 5) -> list[dict]:
    """Find the job postings that best match a resume. Pass the full resume text.
    Each result also lists which of the job's skills the resume already has."""
    resume_skills = set(extract_skills(resume_text))
    jobs = search_jobs(resume_text, limit)  # a resume is just a long search query
    for job in jobs:
        job["matching_skills"] = sorted(resume_skills & set(job["skills"]))
    return jobs


def skill_gap(resume_text: str, job_id: int) -> dict:
    """Compare a resume against one job posting. Returns the skills the candidate
    already has, the skills that are missing, and a match percentage."""
    job = get_job(job_id)
    if "error" in job:
        return job
    job_skills = set(job["skills"])
    resume_skills = set(extract_skills(resume_text))
    have = sorted(job_skills & resume_skills)
    missing = sorted(job_skills - resume_skills)
    percent = round(100 * len(have) / len(job_skills)) if job_skills else 0
    return {"job_id": job_id, "title": job["title"], "company": job["company"],
            "have": have, "missing": missing, "match_percent": percent}


def interview_prep(job_id: int) -> dict:
    """Get the material needed to prepare for an interview for one job: the role,
    the skills to revise, and the posting text. Use this, then write practice questions from it."""
    job = get_job(job_id)
    if "error" in job:
        return job
    return {"job_id": job_id, "title": job["title"], "company": job["company"],
            "skills_to_revise": job["skills"], "posting": job["description"],
            "question_types": ["technical question per skill", "one project deep-dive",
                               "one behavioural question", "one question to ask the interviewer"]}


ALL_TOOLS = [search_jobs, get_job, match_resume, skill_gap, interview_prep]
