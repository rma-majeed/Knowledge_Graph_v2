"""End-to-end document ingestion pipeline.

Wires: extraction (PDF/PPTX) -> chunking (tiktoken) -> storage (SQLite)

Usage:
    from src.ingest.pipeline import ingest_document, ingest_directory

    # Single file
    result = ingest_document("report.pdf", db_path="data/chunks.db")
    print(f"Inserted {result['chunks_inserted']} chunks")

    # Directory batch
    results = ingest_directory("documents/", db_path="data/chunks.db")
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

from tqdm import tqdm

from src.ingest.chunker import chunk_text
from src.ingest.pdf_extractor import extract_pdf
from src.ingest.pptx_extractor import extract_pptx
from src.ingest.store import ChunkStore, compute_file_hash

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".pdf", ".pptx"}


def _ingest_llm_model() -> str:
    """Return the LLM model name for use during enrichment. Reads env or defaults."""
    import os
    return os.getenv("LLM_MODEL", "Qwen2.5-7B-Instruct")


def ingest_document(
    filepath: Union[str, Path],
    db_path: Union[str, Path],
    chunk_size: int = 512,
    overlap: int = 100,
) -> dict:
    """Ingest a single PDF or PPTX document into the SQLite chunk store.

    Full pipeline: validate -> deduplicate -> extract -> chunk -> store.

    Args:
        filepath: Path to the PDF or PPTX file.
        db_path: Path to the SQLite database file (created if not exists).
        chunk_size: Tokens per chunk (default: 512).
        overlap: Overlap tokens between adjacent chunks (default: 100).

    Returns:
        Dict with keys:
        - "doc_id": int | None -- doc_id assigned if newly ingested; None if skipped
        - "chunks_inserted": int -- number of chunks written to DB
        - "skipped": bool -- True if document was already indexed (dedup)
        - "filename": str -- base filename of the document

    Raises:
        ValueError: If file extension is not .pdf or .pptx.
        FileNotFoundError: If file does not exist.
    """
    filepath = Path(filepath)
    db_path = Path(db_path)

    if not filepath.exists():
        raise FileNotFoundError(f"Document not found: {filepath}")

    suffix = filepath.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix!r}. Supported: {_SUPPORTED_EXTENSIONS}"
        )

    # Open DB connection (creates file if not exists)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance in Phase 2+
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        store = ChunkStore(conn)
        store.init_schema()
        # Phase 7: ensure Phase 7 schema additions are present
        store.add_enriched_text_column()

        # Deduplication check
        if store.is_document_indexed(filepath):
            return {
                "doc_id": None,
                "chunks_inserted": 0,
                "skipped": True,
                "filename": filepath.name,
            }

        # Extract text from document
        if suffix == ".pdf":
            pages = extract_pdf(filepath)
            doc_type = "pdf"
            total_pages = len(pages)
            # Normalize: PDF pages use "page_num" key (already 1-indexed)
            page_items = [{"page_num": p["page_num"], "text": p["text"]} for p in pages]
        else:  # .pptx
            slides = extract_pptx(filepath)
            doc_type = "pptx"
            total_pages = len(slides)
            # Normalize: PPTX uses "slide_num" -> map to "page_num" for uniform storage
            page_items = [{"page_num": s["slide_num"], "text": s["text"]} for s in slides]

        # Insert document record
        file_hash = compute_file_hash(filepath)
        doc_id = store.insert_document(
            filename=filepath.name,
            file_size_bytes=filepath.stat().st_size,
            file_hash=file_hash,
            doc_type=doc_type,
            total_pages=total_pages,
        )

        # Chunk each page/slide and collect all chunks with page_num
        all_chunks: list[dict] = []
        for item in page_items:
            text = item["text"].strip()
            if not text:
                continue  # Skip empty pages/slides

            page_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            for chunk in page_chunks:
                all_chunks.append(
                    {
                        "page_num": item["page_num"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "token_count": chunk["token_count"],
                    }
                )

        # Phase 7 RAG-03: contextual chunk enrichment (optional, opt-in)
        from src.config.retrieval_config import RAG_ENABLE_ENRICHMENT
        if RAG_ENABLE_ENRICHMENT and all_chunks:
            from src.ingest.enricher import enrich_chunk_context
            from src.config.providers import get_llm_client
            try:
                llm_client = get_llm_client()
                enrichment_model = _ingest_llm_model()
                enriched = []
                for chunk in all_chunks:
                    enriched_text = enrich_chunk_context(chunk["text"], llm_client, enrichment_model)
                    enriched.append({**chunk, "enriched_text": enriched_text})
                all_chunks = enriched
            except Exception:
                pass  # enrichment failure must never block ingest

        # Bulk insert all chunks
        if all_chunks:
            store.insert_chunks(doc_id, all_chunks)
            # Phase 7 RAG-04: parent-document mapping (optional, enabled by default)
            from src.config.retrieval_config import RAG_ENABLE_PARENT_DOC
            if RAG_ENABLE_PARENT_DOC:
                # Fetch chunk_ids just inserted for this doc_id
                inserted_rows = conn.execute(
                    "SELECT chunk_id, chunk_text, token_count FROM chunks WHERE doc_id = ?",
                    (doc_id,),
                ).fetchall()
                parent_rows = []
                for r in inserted_rows:
                    if hasattr(r, "keys"):
                        parent_rows.append({"chunk_id": r["chunk_id"], "text": r["chunk_text"] or "", "token_count": r["token_count"] or 0})
                    else:
                        parent_rows.append({"chunk_id": r[0], "text": r[1] or "", "token_count": r[2] or 0})
                store.insert_chunk_parents(doc_id, parent_rows)

        return {
            "doc_id": doc_id,
            "chunks_inserted": len(all_chunks),
            "skipped": False,
            "filename": filepath.name,
        }

    finally:
        conn.close()


def ingest_directory(
    folder_path: Union[str, Path],
    db_path: Union[str, Path],
    chunk_size: int = 512,
    overlap: int = 100,
) -> list[dict]:
    """Ingest all PDF and PPTX files in a folder (non-recursive).

    Args:
        folder_path: Directory containing documents to ingest.
        db_path: Path to the SQLite database file.
        chunk_size: Tokens per chunk (default: 512).
        overlap: Overlap tokens between adjacent chunks (default: 100).

    Returns:
        List of result dicts from ingest_document(), one per file.
        Includes both ingested and skipped (deduplicated) files.
    """
    folder_path = Path(folder_path)
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    # Collect supported files (sorted for deterministic order)
    files = sorted(
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
    )

    if not files:
        return []

    results: list[dict] = []
    for filepath in tqdm(files, desc="Ingesting documents", unit="doc", disable=len(files) == 1):
        result = ingest_document(
            filepath, db_path=db_path, chunk_size=chunk_size, overlap=overlap
        )
        results.append(result)

    return results
