"""
Real job postings from LinkedIn.

LinkedIn shows job postings to visitors who are not logged in. Those public
pages load their data from two addresses, and this file reads both:

  1. SEARCH_URL   HTML with 10 job cards: title, company, location, logo, date, job id
  2. POSTING_URL  HTML for one posting, with the full description

BeautifulSoup reads the HTML. We wait between requests so we don't overload
LinkedIn. Keep it small: LinkedIn's terms don't allow bulk scraping.
"""
import re
import time

import httpx
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
POSTING_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}

# Each category is searched with these phrases. The category is saved with every
# posting, and eval_retrieval.py uses it as the correct answer.
SEARCHES = {
    "frontend": ["frontend developer intern", "react developer intern"],
    "backend": ["backend developer intern", "backend engineer intern"],
    "data": ["machine learning intern", "data science intern"],
    "devops": ["devops intern", "cloud engineer intern"],
    "mobile": ["mobile developer intern", "ios developer intern", "android developer intern"],
    "security": ["cybersecurity intern", "security analyst intern"],
}


def get_html(url: str, params: dict | None = None) -> str:
    """Download one page. Wait first so we don't overload LinkedIn, and wait
    longer if it answers 429 ("too many requests")."""
    for wait in (1.5, 10, 30):
        time.sleep(wait)
        response = httpx.get(url, params=params, headers=HEADERS, timeout=20, follow_redirects=True)
        if response.status_code != 429:
            return response.text if response.status_code == 200 else ""
    return ""


def text_of(card, css_selector: str) -> str:
    element = card.select_one(css_selector)
    return " ".join(element.get_text().split()) if element else ""


def parse_search_page(html: str) -> list[dict]:
    """The job cards on one page of search results."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("div.base-card[data-entity-urn]"):
        job_id = card["data-entity-urn"].split(":")[-1]  # "urn:li:jobPosting:4480192634" -> "4480192634"
        logo = card.select_one("img[data-delayed-url]")
        date = card.select_one("time")
        jobs.append({
            "external_id": job_id,
            "title": text_of(card, ".base-search-card__title"),
            "company": text_of(card, ".base-search-card__subtitle"),
            "location": text_of(card, ".job-search-card__location"),
            "posted_at": date["datetime"] if date else None,
            "logo_url": logo["data-delayed-url"] if logo else "",
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
        })
    return jobs


def parse_description(html: str) -> str:
    """The description of one posting as plain text: line breaks kept, list items as bullets."""
    box = BeautifulSoup(html, "html.parser").select_one(".show-more-less-html__markup")
    if box is None:
        return ""
    for br in box.find_all("br"):
        br.replace_with("\n")
    for item in box.find_all("li"):
        item.insert(0, "\n• ")
    for paragraph in box.find_all("p"):
        paragraph.append("\n")
    lines = [" ".join(line.split()) for line in box.get_text().splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()  # at most one blank line in a row


def is_english(text: str) -> bool:
    """Searches in Canada return many French postings, and the embedding model only
    knows English. Count a few very common French and English words."""
    words = text.lower().split()
    french = sum(words.count(w) for w in ("le", "la", "les", "des", "et", "vous", "nous", "pour", "avec"))
    english = sum(words.count(w) for w in ("the", "and", "you", "we", "with", "for", "our", "to", "of"))
    return english > french


def fetch_postings(query: str, category: str, how_many: int = 12) -> list[dict]:
    """Search LinkedIn, then open each posting to get its description."""
    jobs = []
    for start in range(0, how_many, 10):  # each search page has 10 cards
        html = get_html(SEARCH_URL, {"keywords": query, "location": "Canada", "start": start})
        jobs += parse_search_page(html)
    jobs = jobs[:how_many]

    for job in jobs:
        job["description"] = parse_description(get_html(POSTING_URL.format(job_id=job["external_id"])))
        job["category"] = category
        job["source"] = "linkedin"
        print(f"  {job['title']} at {job['company']}")
    return [job for job in jobs if job["description"] and is_english(job["title"] + " " + job["description"])]


def fetch_all() -> list[dict]:
    """Run every search in SEARCHES. A job found twice is kept once: the same job
    listed in another city has a new id, but the same company and title."""
    all_jobs, seen = [], set()
    for category, queries in SEARCHES.items():
        for query in queries:
            print(f"Searching LinkedIn for {query!r}")
            for job in fetch_postings(query, category):
                if (job["company"], job["title"]) not in seen:
                    seen.add((job["company"], job["title"]))
                    all_jobs.append(job)
    return all_jobs
