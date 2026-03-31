-- Automotive Consulting GraphRAG — Phase 1 SQLite Schema
-- This file is the source of truth. ChunkStore.init_schema() executes this.

CREATE TABLE IF NOT EXISTS documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER,
    file_hash TEXT NOT NULL UNIQUE,  -- SHA-256 hex (64 chars) for deduplication
    doc_type TEXT NOT NULL,          -- 'pdf' or 'pptx'
    total_pages INTEGER,             -- Total page or slide count
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP             -- NULL until embedding phase marks complete
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    page_num INTEGER,       -- 1-indexed page (PDF) or slide (PPTX) number
    chunk_index INTEGER,    -- 0-indexed position within the document
    chunk_text TEXT NOT NULL,
    token_count INTEGER,    -- Token count via tiktoken cl100k_base
    embedding_flag INTEGER DEFAULT 0,  -- 0=pending, 1=embedded, -1=skip
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page_num ON chunks(doc_id, page_num);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_flag ON chunks(embedding_flag);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_page_index ON chunks(doc_id, page_num, chunk_index);

-- Metadata table: stores key/value pairs for pipeline state tracking.
-- Used to detect embedding model changes between runs (PROVIDER-06).
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Phase 7 RAG-04: parent-document retrieval table
-- v1 identity mapping: child_chunk_id == parent_chunk_id.
-- Future: insert smaller child chunks pointing to 512-token parents.
CREATE TABLE IF NOT EXISTS chunk_parents (
    child_chunk_id  INTEGER PRIMARY KEY,
    parent_chunk_id INTEGER NOT NULL,
    parent_text     TEXT NOT NULL,
    parent_token_count INTEGER,
    FOREIGN KEY (child_chunk_id)  REFERENCES chunks(chunk_id),
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
);
