"""
Measure retrieval quality: keyword search vs pgvector embedding search.

    python eval_retrieval.py

Metric: Recall@5. For each query we know which sample jobs are relevant (the 4
jobs in that category). Recall@5 = how many of those 4 show up in the top 5.
The queries are written in everyday words that mostly do NOT appear in the
postings, which is exactly where keyword search struggles.

This runs on the 24 invented sample postings, so treat the result as a small
sanity check. A number you quote should come from a bigger, real dataset.
"""
from app.db import connect
from app.ingest import ingest, load_sample
from app.tools import search_jobs

QUERIES = [
    ("making websites look good and work in the browser", "frontend"),
    ("building the visual part of web apps that users click on", "frontend"),
    ("writing server code and database queries behind an app", "backend"),
    ("designing endpoints that other programs call", "backend"),
    ("teaching computers to learn patterns from data", "data"),
    ("analysing numbers and building predictive models", "data"),
    ("automating how software gets shipped to servers", "devops"),
    ("keeping cloud systems running and monitored", "devops"),
    ("making apps for phones", "mobile"),
    ("iPhone and Android app development", "mobile"),
    ("protecting systems from hackers", "security"),
    ("finding vulnerabilities and responding to attacks", "security"),
]


def keyword_search(query: str, limit: int = 5) -> list[dict]:
    """Baseline: PostgreSQL full-text search. Matches postings sharing words with the query."""
    with connect() as conn:
        return conn.execute(
            """
            SELECT id, category,
                   ts_rank(to_tsvector('english', title || ' ' || description),
                           to_tsquery('english', %s)) AS rank
            FROM jobs
            WHERE to_tsvector('english', title || ' ' || description) @@ to_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (_or_query(query), _or_query(query), limit),
        ).fetchall()


def _or_query(query: str) -> str:
    # "phones apps" -> "phones | apps": match postings containing ANY of the words
    return " | ".join(word for word in query.replace("'", "").split() if word.isalnum())


def recall_at_5(search, relevant_ids: set[int], query: str) -> float:
    found = {row["id"] for row in search(query, 5)}
    return len(found & relevant_ids) / len(relevant_ids)


if __name__ == "__main__":
    ingest(load_sample())
    with connect() as conn:
        rows = conn.execute("SELECT id, category FROM jobs").fetchall()
    by_category: dict[str, set[int]] = {}
    for row in rows:
        by_category.setdefault(row["category"], set()).add(row["id"])

    keyword_scores, vector_scores = [], []
    print(f"{'query':58} keyword  vector")
    for query, category in QUERIES:
        k = recall_at_5(keyword_search, by_category[category], query)
        v = recall_at_5(search_jobs, by_category[category], query)
        keyword_scores.append(k)
        vector_scores.append(v)
        print(f"{query[:56]:58} {k:6.2f}  {v:6.2f}")

    keyword_avg = sum(keyword_scores) / len(keyword_scores)
    vector_avg = sum(vector_scores) / len(vector_scores)
    print(f"\nMean Recall@5   keyword: {keyword_avg:.3f}   pgvector: {vector_avg:.3f}")
    if keyword_avg > 0:
        print(f"Relative change: {100 * (vector_avg - keyword_avg) / keyword_avg:+.0f}%")
