"""
Measure retrieval quality: keyword search vs pgvector embedding search.

    python eval_retrieval.py

Runs on whatever postings are loaded and does not change the database.

How relevance is decided: every posting has a category (frontend, backend, data,
devops, mobile, security). For LinkedIn postings it is the category whose search
found the posting. A result is relevant when its category matches the query's.

Recall@5 = of all the relevant postings, the share that appear in the top 5.
Averaged over the queries.

Half the queries use everyday words ("making apps for phones"), half use the
words a posting would use ("iOS Android mobile developer"), so the test is fair
to keyword search too.
"""
from app.db import connect
from app.tools import search_jobs

QUERIES = [
    ("making websites look good and work in the browser", "frontend"),
    ("building the visual part of web apps that users click on", "frontend"),
    ("React TypeScript frontend developer", "frontend"),
    ("JavaScript CSS user interface engineer", "frontend"),
    ("writing server code and database queries behind an app", "backend"),
    ("designing endpoints that other programs call", "backend"),
    ("backend developer APIs databases", "backend"),
    ("Java Python backend services SQL", "backend"),
    ("teaching computers to learn patterns from data", "data"),
    ("analysing numbers and building predictive models", "data"),
    ("machine learning data science intern", "data"),
    ("Python pandas statistics models", "data"),
    ("automating how software gets shipped to servers", "devops"),
    ("keeping cloud systems running and monitored", "devops"),
    ("DevOps CI/CD Docker Kubernetes", "devops"),
    ("cloud infrastructure AWS Azure engineer", "devops"),
    ("making apps for phones", "mobile"),
    ("building something people use on their iPhone", "mobile"),
    ("iOS Android mobile developer", "mobile"),
    ("Swift Kotlin mobile app", "mobile"),
    ("protecting systems from hackers", "security"),
    ("finding weaknesses and responding to attacks", "security"),
    ("cybersecurity analyst", "security"),
    ("security vulnerability network SIEM", "security"),
]


def keyword_search(query: str, limit: int = 5) -> list[dict]:
    """Baseline: PostgreSQL full-text search. Matches postings sharing words with the query."""
    words = " | ".join(w for w in query.replace("/", " ").split() if w.isalnum())  # "apps | phones": ANY word
    with connect() as conn:
        return conn.execute(
            """
            SELECT id FROM jobs
            WHERE to_tsvector('english', title || ' ' || description) @@ to_tsquery('english', %s)
            ORDER BY ts_rank(to_tsvector('english', title || ' ' || description), to_tsquery('english', %s)) DESC
            LIMIT %s
            """,
            (words, words, limit),
        ).fetchall()


def recall_at_5(search, query: str, relevant: set[int]) -> float:
    found = {row["id"] for row in search(query, 5)}
    return len(found & relevant) / len(relevant)


if __name__ == "__main__":
    with connect() as conn:
        rows = conn.execute("SELECT id, category FROM jobs").fetchall()
    by_category: dict[str, set[int]] = {}
    for row in rows:
        by_category.setdefault(row["category"], set()).add(row["id"])

    keyword_scores, vector_scores = [], []
    print(f"{'query':58} keyword  pgvector")
    for query, category in QUERIES:
        k = recall_at_5(keyword_search, query, by_category[category])
        v = recall_at_5(search_jobs, query, by_category[category])
        keyword_scores.append(k)
        vector_scores.append(v)
        print(f"{query[:56]:58} {k:6.2f}  {v:6.2f}")

    keyword_avg = sum(keyword_scores) / len(keyword_scores)
    vector_avg = sum(vector_scores) / len(vector_scores)
    print(f"\nMean Recall@5   keyword: {keyword_avg:.3f}   pgvector: {vector_avg:.3f}")
    print(f"Relative change: {100 * (vector_avg - keyword_avg) / keyword_avg:+.0f}%   ({len(rows)} postings, {len(QUERIES)} queries)")
