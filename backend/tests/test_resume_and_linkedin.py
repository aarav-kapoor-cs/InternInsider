"""
Tests for the two input paths: resume files (text layer and OCR) and LinkedIn
HTML. No network: the LinkedIn tests parse small HTML snippets with the same
structure as LinkedIn's public pages.
"""
import io
import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.db import connect
from app.linkedin import is_english, parse_description, parse_search_page
from app.resume_parser import parse_resume

needs_tesseract = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract is not installed")

RESUME_LINES = [
    "Jordan Lee, Computing Science student",
    "Built REST APIs in Python and FastAPI with PostgreSQL",
    "Packaged services with Docker and tested them with pytest",
]


def text_layer_pdf(lines: list[str]) -> bytes:
    """A one-page PDF WITH a text layer, written by hand so no PDF library is needed."""
    stream = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def scanned_pdf(lines: list[str]) -> bytes:
    """A PDF WITHOUT a text layer: the text is drawn into an image, like a scan."""
    image = Image.new("RGB", (1700, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    for i, line in enumerate(lines):
        draw.text((60, 60 + i * 80), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=200)
    return buffer.getvalue()


# ------------------------------------------------------------- resume files

def test_pdf_with_text_layer_is_read_without_ocr():
    result = parse_resume(text_layer_pdf(RESUME_LINES))
    assert result["method"] == "text"
    assert result["ocr_confidence"] is None
    assert "FastAPI with PostgreSQL" in result["text"]


@needs_tesseract
def test_scanned_pdf_falls_back_to_ocr():
    result = parse_resume(scanned_pdf(RESUME_LINES))
    assert result["method"] == "ocr"
    assert result["ocr_confidence"] > 60
    assert "FastAPI" in result["text"] and "PostgreSQL" in result["text"]


def test_unsupported_file_is_rejected():
    with pytest.raises(ValueError):
        parse_resume(b"this is not a pdf or an image")


@needs_tesseract
def test_upload_endpoint_returns_text_and_skills():
    with TestClient(__import__("app.main").main.app) as client:
        response = client.post("/api/resume/parse",
                               files={"file": ("resume.pdf", scanned_pdf(RESUME_LINES), "application/pdf")})
        assert response.status_code == 200
        body = response.json()
        assert body["method"] == "ocr" and body["filename"] == "resume.pdf"
        assert {"python", "fastapi", "postgresql", "docker"} <= set(body["skills"])
        # The upload was saved to PostgreSQL.
        with connect() as conn:
            row = conn.execute("SELECT filename, method FROM resumes WHERE id = %s", (body["id"],)).fetchone()
        assert row == {"filename": "resume.pdf", "method": "ocr"}
        bad = client.post("/api/resume/parse", files={"file": ("notes.txt", b"hello", "text/plain")})
        assert bad.status_code == 400


# ---------------------------------------------------------------- LinkedIn

SEARCH_HTML = """
<li><div class="base-card job-search-card" data-entity-urn="urn:li:jobPosting:4480192634">
  <img class="artdeco-entity-image" data-delayed-url="https://media.example/logo.png">
  <h3 class="base-search-card__title">  Intern, Software Developer  </h3>
  <h4 class="base-search-card__subtitle"><a>  Acme Aero </a></h4>
  <span class="job-search-card__location"> Montreal, Quebec, Canada </span>
  <time class="job-search-card__listdate" datetime="2026-11-06">4 days ago</time>
</div></li>
"""

POSTING_HTML = """
<div class="show-more-less-html__markup">
  <strong>What you will do</strong><br><br>
  <ul><li>Build features in React &amp; Node.js</li><li>Write unit tests</li></ul>
  <p>We use Python and SQL.</p>
</div>
"""


def test_parse_linkedin_search_page():
    assert parse_search_page(SEARCH_HTML) == [{
        "external_id": "4480192634", "title": "Intern, Software Developer", "company": "Acme Aero",
        "location": "Montreal, Quebec, Canada", "posted_at": "2026-11-06",
        "logo_url": "https://media.example/logo.png", "url": "https://www.linkedin.com/jobs/view/4480192634",
    }]


def test_parse_linkedin_description_keeps_lines_and_bullets():
    assert parse_description(POSTING_HTML) == (
        "What you will do\n\n• Build features in React & Node.js\n• Write unit tests\nWe use Python and SQL.")
    assert parse_description("<html>no description here</html>") == ""


def test_french_postings_are_detected():
    assert is_english("Software Developer Intern. You will build features with our team and ship them to users.")
    assert not is_english("Stagiaire en développement. Vous travaillerez avec une équipe pour le développement des produits.")
