"""
Resume file (PDF or image) to text.

Two ways to get the words out of a page:

  1. Text layer. A PDF made in Word, Google Docs or LaTeX contains the characters
     themselves. pypdfium2 reads them: exact, and takes milliseconds.
  2. OCR. A scanned PDF or a photo is only pixels. We turn the page into an image
     at 300 DPI and Tesseract recognises the letters. Slower (about 1 s a page).

The rule: use the text layer. If a page has almost no text, it is a scan, so use OCR.
"""
import io
import time
import unicodedata

import pypdfium2 as pdfium
import pytesseract
from PIL import Image

MIN_CHARS = 100  # a page with less text than this is treated as a scan


def ocr(image: Image.Image) -> tuple[str, float]:
    """Run Tesseract on one image. Returns the text and the average word confidence (0-100)."""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    lines, scores = {}, []
    # Tesseract returns one entry per word, with the block, paragraph and line it belongs to.
    for word, score, block, paragraph, line in zip(data["text"], data["conf"], data["block_num"],
                                                    data["par_num"], data["line_num"]):
        if word.strip():
            lines.setdefault((block, paragraph, line), []).append(word)
            scores.append(float(score))
    text = "\n".join(" ".join(words) for words in lines.values())
    return text, sum(scores) / max(len(scores), 1)


def parse_resume(data: bytes) -> dict:
    """Read a PDF, PNG or JPG. Returns the text and how it was read."""
    start = time.time()
    texts, methods, scores = [], [], []

    if data.startswith(b"%PDF"):
        pdf = pdfium.PdfDocument(data)
        if len(pdf) > 5:
            raise ValueError("A resume should have at most 5 pages.")
        for page in pdf:
            text = page.get_textpage().get_text_bounded()
            if len(text.strip()) < MIN_CHARS:  # no real text layer: it is a scan
                text, score = ocr(page.render(scale=300 / 72).to_pil())  # PDF units are 1/72 inch
                scores.append(score)
                methods.append("ocr")
            else:
                methods.append("text")
            texts.append(text)
    else:
        try:
            image = Image.open(io.BytesIO(data))
        except Exception:
            raise ValueError("Upload a PDF, PNG or JPG file.")
        text, score = ocr(image)  # a photo has no text layer, so always OCR
        texts, methods, scores = [text], ["ocr"], [score]

    return {
        # NFKC turns LaTeX ligatures like "ﬁ" into plain "fi", so skill words still match.
        "text": unicodedata.normalize("NFKC", "\n\n".join(texts)).strip(),
        "method": methods[0] if len(set(methods)) == 1 else "mixed",  # "text", "ocr" or "mixed"
        "pages": len(texts),
        "ocr_confidence": round(sum(scores) / len(scores), 1) if scores else None,
        "seconds": round(time.time() - start, 2),
    }
