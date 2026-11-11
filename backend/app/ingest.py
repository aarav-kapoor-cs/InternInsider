"""
Load job postings into PostgreSQL: extract skills, compute the embedding, insert.

    python -m app.ingest              load data/sample_jobs.json (invented postings, works offline)
    python -m app.ingest --remotive   fetch real remote software jobs from the public Remotive API
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from app.db import connect, embed, init_db, to_pgvector
from app.skills import extract_skills

SAMPLE_FILE = Path(__file__).parent.parent / "data" / "sample_jobs.json"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=100"


def load_sample() -> list[dict]:
    return json.loads(SAMPLE_FILE.read_text())


def load_remotive() -> list[dict]:
    request = urllib.request.Request(REMOTIVE_URL, headers={"User-Agent": "InternInsider-demo"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    jobs = []
    for item in data["jobs"]:
        text = re.sub(r"<[^>]+>", " ", item["description"])  # strip HTML tags
        text = re.sub(r"\s+", " ", text).strip()[:3000]
        jobs.append({"title": item["title"], "company": item["company_name"],
                     "location": item.get("candidate_required_location", ""),
                     "category": item.get("category", ""), "url": item.get("url", ""),
                     "description": text})
    return jobs


def ingest(jobs: list[dict]) -> int:
    """Replace the jobs table with these postings. Returns how many were inserted."""
    init_db()
    with connect() as conn:
        conn.execute("TRUNCATE jobs RESTART IDENTITY")
        for job in jobs:
            text = job["title"] + ". " + job["description"]
            conn.execute(
                """
                INSERT INTO jobs (title, company, location, category, url, description, skills, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                (job["title"], job["company"], job.get("location", ""), job.get("category", ""),
                 job.get("url", ""), job["description"], extract_skills(text), to_pgvector(embed(text))),
            )
    return len(jobs)


if __name__ == "__main__":
    source = load_remotive if "--remotive" in sys.argv else load_sample
    print(f"Loaded {ingest(source())} job postings.")
