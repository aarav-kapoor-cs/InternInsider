"""
Load job postings into PostgreSQL.

    python -m app.ingest                       the 24 invented sample postings (offline)
    python -m app.ingest --linkedin            fetch real postings from LinkedIn (about 5 min) and save them
    python -m app.ingest --linkedin --cached   load the saved LinkedIn postings again, no network

For each posting: find its skills, turn it into a vector, INSERT it.
"""
import json
import sys
from pathlib import Path

from app.db import connect, embed, init_db, job_text, to_pgvector
from app.skills import extract_skills

DATA = Path(__file__).parent.parent / "data"
LINKEDIN_FILE = DATA / "linkedin_jobs.json"  # not committed: the postings belong to LinkedIn


def load_sample() -> list[dict]:
    return json.loads((DATA / "sample_jobs.json").read_text())


def ingest(jobs: list[dict]) -> int:
    """Rebuild the jobs table with these postings. Returns how many were loaded."""
    with connect() as conn:
        conn.execute("DROP TABLE IF EXISTS jobs")  # start fresh every time
    init_db()
    with connect() as conn:
        for job in jobs:
            skills = extract_skills(job["title"] + "\n" + job["description"])
            vector = to_pgvector(embed(job_text(job["title"], skills, job["description"])))
            conn.execute(
                """
                INSERT INTO jobs (title, company, location, category, url, logo_url, posted_at, source,
                                  description, skills, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                (job["title"], job["company"], job.get("location", ""), job.get("category", ""),
                 job.get("url", ""), job.get("logo_url", ""), job.get("posted_at"), job.get("source", "sample"),
                 job["description"], skills, vector),
            )
    return len(jobs)


if __name__ == "__main__":
    if "--linkedin" not in sys.argv:
        jobs = load_sample()
    elif "--cached" in sys.argv:
        jobs = json.loads(LINKEDIN_FILE.read_text())
    else:
        from app.linkedin import fetch_all

        jobs = fetch_all()
        LINKEDIN_FILE.write_text(json.dumps(jobs, indent=1, ensure_ascii=False))
    print(f"Loaded {ingest(jobs)} job postings.")
