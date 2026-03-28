"""PDF text extraction using PyMuPDF (fitz).

Extracts plain text and table cell content from each page of a PDF document.
Returns a list of page dicts with 1-indexed page numbers.

Usage:
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf("path/to/document.pdf")
    # pages[0] == {"page_num": 1, "text": "..."}
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import fitz  # PyMuPDF


def extract_pdf(filepath: Union[str, Path]) -> list[dict]:
    """Extract text from all pages of a PDF file.

    For each page, extracts:
    - Plain text via page.get_text()
    - Table cell content via page.find_tables() (appended after plain text)

    Args:
        filepath: Path to the PDF file (str or pathlib.Path).

    Returns:
        List of dicts, one per page, in document order:
        [
            {"page_num": 1, "text": "..."},  # 1-indexed
            {"page_num": 2, "text": "..."},
            ...
        ]

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a readable PDF.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"PDF not found: {filepath}")

    doc = fitz.open(str(filepath))
    pages: list[dict] = []

    try:
        for page_idx in range(doc.page_count):
            page = doc[page_idx]

            # Extract plain text (preserves whitespace layout)
            plain_text: str = page.get_text()

            # Extract table cell text and append after plain text
            table_parts: list[str] = []
            try:
                tables = page.find_tables()
                for table in tables:
                    rows = table.extract()  # list[list[str | None]]
                    for row in rows:
                        # Filter None cells, join with tab
                        cells = [cell if cell is not None else "" for cell in row]
                        row_text = "\t".join(cells).strip()
                        if row_text:
                            table_parts.append(row_text)
            except Exception:
                # find_tables can fail on malformed PDFs — degrade gracefully
                pass

            # Combine plain text and table text
            parts = [plain_text.strip()]
            if table_parts:
                parts.append("\n".join(table_parts))
            combined_text = "\n".join(p for p in parts if p)

            pages.append({
                "page_num": page_idx + 1,  # Convert 0-indexed to 1-indexed
                "text": combined_text,
            })
    finally:
        doc.close()

    return pages
