"""Tests for PDF and PPTX text extraction.

Stubs: marked xfail until src/ingest/pdf_extractor.py and
src/ingest/pptx_extractor.py are implemented (Plan 02 and Plan 03).
"""
import pytest


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_text(sample_pdf_path):
    """PDF extractor returns text with page numbers."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    assert len(pages) == 2
    assert pages[0]["page_num"] == 1
    assert "Automotive" in pages[0]["text"]


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_tables(sample_pdf_path):
    """PDF extractor includes table cell text in page output."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    all_text = " ".join(p["text"] for p in pages)
    assert "Toyota" in all_text  # Table cell content


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_returns_page_count(sample_pdf_path):
    """Page count in result matches actual PDF page count."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    assert len(pages) == 2


def test_pptx_extract_slides(sample_pptx_path):
    """PPTX extractor returns text for each slide with slide numbers."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    assert len(slides) == 3
    assert slides[0]["slide_num"] == 1
    assert "EV Strategy" in slides[0]["text"]


def test_pptx_extract_notes(sample_pptx_path):
    """PPTX extractor includes speaker notes in slide output."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    # Slide 1 has notes
    assert "Speaker note" in slides[0]["text"] or "Emphasize" in slides[0]["text"]


def test_pptx_extract_tables(sample_pptx_path):
    """PPTX extractor includes table cell text from slide 3."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    all_text = " ".join(s["text"] for s in slides)
    assert "Battery Partner" in all_text  # Table header cell
    assert "Panasonic" in all_text         # Table data cell
