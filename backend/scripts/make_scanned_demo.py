"""
Make the demo file frontend/public/demo/scanned-resume.pdf: a resume for an
invented student, drawn into an image and saved as a PDF with NO text layer,
like a phone scan. Uploading it forces the OCR path.

    cd backend && python scripts/make_scanned_demo.py
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "scanned-resume.pdf"

# DEMO ONLY: an invented person.
LINES = [
    ("title", "JORDAN LEE"),
    ("small", "Computing Science student  |  jordan.lee@example.com  |  Edmonton, AB"),
    ("gap", ""),
    ("head", "EDUCATION"),
    ("body", "BSc Computing Science, University of Alberta (expected 2028)"),
    ("gap", ""),
    ("head", "EXPERIENCE"),
    ("body", "Software Developer Intern, Prairie Analytics (Summer 2026)"),
    ("body", "- Built REST APIs in Python and FastAPI backed by PostgreSQL"),
    ("body", "- Packaged services with Docker and wrote unit tests with pytest"),
    ("body", "- Added a React and TypeScript dashboard for weekly reports"),
    ("gap", ""),
    ("head", "PROJECTS"),
    ("body", "Campus Events: a React Native app with Firebase sign-in"),
    ("body", "Stock Trends: pandas, scikit-learn and SQL on public market data"),
    ("gap", ""),
    ("head", "SKILLS"),
    ("body", "Python, TypeScript, SQL, React, FastAPI, PostgreSQL, Docker, Git, Linux, AWS"),
]


def font(size: int, bold: bool = False):
    candidates = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
                  "/Library/Fonts/Arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def main():
    random.seed(7)
    width, height = 1700, 2200  # US Letter at 200 DPI
    page = Image.new("L", (width, height), 246)  # slightly grey paper
    draw = ImageDraw.Draw(page)
    styles = {"title": (font(64, True), 0), "small": (font(30), 50), "head": (font(36, True), 20),
              "body": (font(34), 30)}
    y = 150
    for kind, text in LINES:
        if kind == "gap":
            y += 30
            continue
        f, ink = styles[kind]
        draw.text((140, y), text, font=f, fill=ink)
        y += int(f.size * 1.6)
        if kind == "head":
            draw.line((140, y - 14, width - 140, y - 14), fill=90, width=2)

    # Make it look scanned: a small tilt, blur and paper noise.
    page = page.rotate(0.7, resample=Image.BICUBIC, fillcolor=246)
    page = page.filter(ImageFilter.GaussianBlur(0.6))
    noise = Image.effect_noise((width, height), 14)
    page = Image.blend(page, noise.convert("L"), 0.06)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    page.convert("RGB").save(OUT, "PDF", resolution=200)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
