import pdfplumber
import os
import re
import fitz # PyMuPDF
import logging

logger = logging.getLogger(__name__)

def get_pdf_page_count(pdf_path: str) -> int:
    """Return total pages for a PDF, or 0 on failure."""
    if not os.path.exists(pdf_path):
        return 0
    try:
        with fitz.open(pdf_path) as doc:
            return len(doc)
    except Exception as e:
        logger.error(f"PyMuPDF page count error: {e}")
        return 0


def parse_lal_kitab_tables(pdf_path, page_start: int = 1, page_end: int | None = None):
    projects = []
    garbled_pages = []
    if not os.path.exists(pdf_path):
        return [], []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            if total_pages == 0:
                return [], []

            start = max(1, int(page_start or 1))
            end = total_pages if page_end is None else min(total_pages, int(page_end))
            if start > end:
                return [], []

            # pdfplumber pages are 0-indexed in list access; page.page_number is 1-indexed.
            selected_pages = pdf.pages[start - 1 : end]
            for page in selected_pages:
                text = page.extract_text()
                if not text or "(cid:" in text or len(re.findall(r'[^\w\s,.]', text)) > len(text) * 0.3:
                    garbled_pages.append(page.page_number)
                    continue

                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            if "????" in row[1] or "??????" in row[0]:
                                continue
                            projects.append({
                                "title_ne": row[0].replace("\n", " ").strip(),
                                "budget": row[1].replace(",", "").strip(),
                                "page_num": page.page_number,
                                "budget_source": "deterministic",
                            })
    except Exception as e:
        logger.error(f"pdfplumber error: {e}")
        
    return projects, garbled_pages

def extract_garbled_pages_as_images(pdf_path, page_numbers):
    """Extracts PDF pages as images using PyMuPDF (no poppler needed)."""
    images = []
    try:
        doc = fitz.open(pdf_path)
        for pg_num in page_numbers:
            if pg_num <= len(doc):
                page = doc.load_page(pg_num - 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 2x zoom
                images.append((pg_num, pix.tobytes("jpg")))
        doc.close()
    except Exception as e:
        logger.error(f"PyMuPDF error: {e}")
    return images

def parse_vision_response(response_text):
    import json
    try:
        cleaned = response_text.replace('`json', '').replace('`', '').strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            for row in parsed:
                if isinstance(row, dict):
                    row["budget_source"] = "vision"
        return parsed
    except:
        return []



