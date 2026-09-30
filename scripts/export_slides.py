"""Exports the hackathon slide deck to docs/slides/SayQL-deck.pdf.

One PDF page per slide, at 1920x1080, with every reveal step already
expanded. Uses the browser's own print pipeline (Chromium's @media print
CSS in docs/slides/index.html), so this does not depend on any on-screen
key having been pressed first.

Requires the FastAPI app running locally with /slides mounted (see README:
`uvicorn main:app`), since this script only drives a browser against it.
"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "docs" / "slides" / "SayQL-deck.pdf"
DEFAULT_URL = "http://127.0.0.1:8000/slides/"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(300)

        slide_count = page.eval_on_selector_all(".slide", "els => els.length")

        page.pdf(
            path=str(OUT_PATH),
            width="1920px",
            height="1080px",
            print_background=True,
        )
        browser.close()

    page_count = _pdf_page_count(OUT_PATH)
    print("wrote", OUT_PATH)
    print("slides in deck:", slide_count)
    print("pages in pdf:", page_count)
    if page_count != slide_count:
        raise SystemExit(
            f"page count mismatch: {page_count} pdf pages vs {slide_count} slides"
        )


def _pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except ImportError:
        out = subprocess.run(
            ["python3", "-c", f"import re,sys; print(len(re.findall(rb'/Type\\s*/Page[^s]', open('{path}','rb').read())))"],
            capture_output=True,
            text=True,
        )
        return int(out.stdout.strip())


if __name__ == "__main__":
    main()
