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
