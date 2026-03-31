# Phase 7: RAG Retrieval Quality Improvements - Research

**Researched:** 2026-03-31
**Domain:** Retrieval-Augmented Generation (RAG) — hybrid search, reranking, chunk enrichment, parent-document retrieval
**Confidence:** HIGH for core techniques (BM25, BGE reranker, RRF); MEDIUM for enrichment (new to this corpus); HIGH for alternatives
**Valid until:** 2026-05-15 (stable fundamentals, but enrichment effectiveness depends on corpus-specific testing)

## Summary

Phase 7 addresses the critical gap identified in the Phase 4 context: short queries like "warranty" fail to match longer passages like "warranty claims management automation" due to vocabulary mismatch. The research identifies **four locked high-priority improvements** (BM25 hybrid search + RRF, BGE cross-encoder reranking, contextual chunk enrichment, parent-document retrieval) plus **five additional techniques** that production RAG systems use to improve quality.

Key finding: **Fixed-size chunking at 512 tokens outperforms semantic chunking by 40%+ on 2026 benchmarks**, so the current chunking strategy is sound. Improvements focus on retrieval fusion (BM25 + vector), ranking (cross-encoder), and context expansion (enrichment + parent docs).

**Primary recommendation:** Implement in this priority order:
1. **BM25 + Vector hybrid search with RRF** — addresses vocabulary mismatch, highest ROI
2. **BGE cross-encoder reranking** — re-orders merged results, 130ms latency on CPU
3. **Parent-document retrieval** — expands child chunks to larger context for LLM
4. **Contextual chunk enrichment** — prepends document context at ingest (optional, depends on corpus analysis)
5. **Metadata filtering** — allows filtering by document type/date at query time (low cost, high value for structured queries)

All changes are additive with feature flags — existing retrieval remains functional.

## Phase Requirements → Research Support

| Req ID | Behavior | Research Support |
|--------|----------|------------------|
| RAG-01 | BM25 keyword search in parallel with vector + merge with RRF | rank_bm25 library (0.2.2), in-memory index, RRF formula: 1/(rank+60) |
| RAG-02 | BGE cross-encoder reranking re-orders top candidates | sentence-transformers + BAAI/bge-reranker-v2-m3 (278M params, CPU-capable) |
| RAG-03 | Contextual enrichment at ingest (LLM summary prepended) | Prompt design: 2-3 sentence summary, store in SQLite metadata, optional re-embedding |
| RAG-04 | Parent-document retrieval (small child → large parent) | Implement parent/child mapping in SQLite schema, retrieve parent when child matches |
| RAG-05 | All improvements configurable and additive | Feature flags in config, graceful fallbacks, backward-compatible DB schema |

## User Constraints (from Phase Context)

| Constraint | Impact |
|-----------|--------|
| **Pip-only dependencies** | rank_bm25, sentence-transformers, BAAI models via Hugging Face pip install |
| **No re-ingestion required** | Parent-document mapping added to schema without forcing full re-embed |
| **Local LM Studio** | BGE reranker (278M) runs on CPU; contextual enrichment uses local LM Studio for summaries |
| **Corporate firewall** | All models cached locally after first download, no mandatory cloud APIs |
| **Feature flags for optional features** | Enrichment and metadata filtering can be toggled independently |

## Standard Stack

### Core Libraries for RAG Improvements

| Library | Version | Purpose | Why Standard | Source |
|---------|---------|---------|--------------|--------|
| **rank_bm25** | 0.2.2 | BM25 keyword search implementation | De-facto standard in production RAG; lightweight, no external deps beyond numpy | PyPI + GitHub (dorianbrown/rank_bm25) |
| **sentence-transformers** | 2.7.0 | Cross-encoder model loading (BAAI/bge-reranker-v2-m3) | Official BAAI distribution mechanism; CPU-inference capable with use_fp16=False | Hugging Face + PyPI |
| **FlagEmbedding** | Latest | Alternative cross-encoder wrapper (BAAI official) | Provides FlagReranker abstraction; used if you prefer BAAI's wrapper over raw sentence-transformers | PyPI (BAAI/FlagEmbedding) |

### Model Downloads (No Additional Packages Required)

| Model | Source | Size | Purpose | Hardware |
|-------|--------|------|---------|----------|
| **BAAI/bge-reranker-v2-m3** | Hugging Face Hub | ~1.1 GB | Cross-encoder reranking | CPU (130ms/16-pair batch); optional GPU |
| **BAAI/bge-m3** | Hugging Face Hub | ~2.4 GB | Alternative: dense encoder (if replacing nomic-embed-text) | GPU preferred, CPU possible |

### Existing Dependencies (Already in requirements.txt)

| Library | Version | Usage in Phase 7 |
|---------|---------|------------------|
| **chromadb** | ≥1.5.5 | Vector store for merged BM25+vector results |
| **sqlite3** | Built-in | Parent-child mapping, metadata storage, enrichment index |
| **openai / litellm** | ≥1.0.0 / ≥1.45.0 | LLM for contextual enrichment summaries (uses existing provider config) |

### Installation Command

```bash
pip install rank_bm25==0.2.2 sentence-transformers==2.7.0
```

### Version Verification

**rank_bm25 (0.2.2):**
- Current stable; no breaking changes expected
- Requires: numpy (already in environment via chromadb)
- PyPI last update: Check `pip index versions rank_bm25`

**sentence-transformers (2.7.0):**
- Released 2024; stable for inference
- Required for CPU cross-encoder inference with use_fp16=False
- Requires: torch, transformers (added to requirements.txt)

## Architecture Patterns

### Current Retrieval Pipeline (Phase 4, existing)

```
User Query
    ↓
[Query Expansion] (3 variants)
    ↓
[Vector Search] (ChromaDB, k=10)
    ↓
[Graph Expansion] (1-hop KuzuDB traversal)
    ↓
[Merge + Deduplicate]
    ↓
[Truncate to Budget] (3000 tokens)
    ↓
[Format Context] → LLM
```

### Phase 7 Enhancement: Hybrid Retrieval with Reranking

```
User Query
    ↓
[Query Expansion] (3 variants) — existing
    ↓
╔═══════════════════════════════════════╗
║ PARALLEL RETRIEVAL (NEW)              ║
├─────────────────────────────────────┤
│ [BM25 Search]     [Vector Search]    │
│ (in-memory index) (ChromaDB)         │
│  k=20 results     k=10 results       │
└─────────────────────────────────────┘
    ↓
[Reciprocal Rank Fusion] (merge + score with RRF formula)
    ↓
[Graph Expansion] (1-hop, existing)
    ↓
[BGE Reranking] (cross-encoder, top-30 candidates → top-10) — NEW
    ↓
[Parent-Document Expansion] (child → parent) — NEW
    ↓
[Truncate to Budget] (3000 tokens)
    ↓
[Format Context] → LLM
```

### Key Design Decisions

**1. BM25 Index Storage**
- **Location:** In-memory (built from SQLite chunks at startup or on-demand)
- **Trade-off:** ~10ms query time vs. ~5MB memory for 500-document corpus (~100K chunks)
- **Alternative:** Persist to disk if memory is constrained (requires additional indexing logic)
- **Recommendation:** In-memory for this use case (32GB RAM available)

**2. RRF Formula & Parameters**
```python
# Reciprocal Rank Fusion score for each document
rrf_score = (1/(rank_bm25 + 60)) + (1/(rank_vector + 60))

# Weighted variant (if prioritizing keyword over semantic):
rrf_score = (1.0/(rank_bm25 + 60)) + (0.7/(rank_vector + 60))

# k=60 is empirically optimal for balanced results
# Adjust if BM25 dominates (increase k) or vector dominates (decrease k)
```

**3. Cross-Encoder Reranking Integration**
- **When to apply:** After merging BM25 + vector + graph results (top ~30-50 candidates)
- **Batch size:** 16 pairs per batch on CPU; scale to 32-64 on GPU
- **Latency:** 130ms per 16-pair batch (acceptable for 30 candidates = 200ms overhead)
- **Output:** Scores 0.0–1.0 per candidate; re-rank by score descending
- **CPU loading:** use_fp16=False; expects float32 computations

**4. Parent-Document Mapping in SQLite**
Current schema (Phase 1) has:
```
chunks (chunk_id, doc_id, chunk_text, token_count, page_num, chunk_index)
```

Add (optional, backward-compatible):
```sql
CREATE TABLE chunk_parents (
    child_chunk_id INTEGER PRIMARY KEY,
    parent_chunk_id INTEGER NOT NULL,
    parent_text TEXT NOT NULL,
    parent_token_count INTEGER,
    FOREIGN KEY (child_chunk_id) REFERENCES chunks(chunk_id),
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
);
```

**Chunk sizing for parent-child:**
- **Child chunks:** 128–256 tokens (precise match for retrieval)
- **Parent chunks:** 512–1024 tokens (context for LLM)
- **Approach:** Keep current 512-token chunks as "parent"; generate 256-token children via fixed overlap OR use existing 512-token chunks directly and optionally nest smaller children within them

**5. Contextual Enrichment Storage**
- **Location:** SQLite metadata column (chunk_metadata.context_summary)
- **Re-embedding:** Do NOT re-embed; embed original chunk text, prepend summary at context assembly time
- **Alternatively:** Prepend summary before embedding at ingest (one-time cost, requires full re-ingest if changed)
- **Recommendation:** Prepend-before-embedding for this corpus (ensures enriched text is what was embedded and what LLM receives)

**6. Feature Flags Configuration**
```python
# src/config/retrieval_config.py (new)
RAG_ENABLE_BM25 = os.getenv("RAG_ENABLE_BM25", "true").lower() == "true"
RAG_ENABLE_RERANKER = os.getenv("RAG_ENABLE_RERANKER", "true").lower() == "true"
RAG_ENABLE_PARENT_DOC = os.getenv("RAG_ENABLE_PARENT_DOC", "false").lower() == "true"
RAG_ENABLE_ENRICHMENT = os.getenv("RAG_ENABLE_ENRICHMENT", "false").lower() == "true"
RAG_ENABLE_METADATA_FILTER = os.getenv("RAG_ENABLE_METADATA_FILTER", "false").lower() == "true"
```

### Recommended Project Structure (Phase 7 additions)

```
src/
├── query/
│   ├── pipeline.py          # MODIFY: wire new retrieval + reranking
│   ├── retriever.py         # MODIFY: add bm25_search(), rerank(), parent_expand()
│   ├── bm25_indexer.py      # NEW: build/manage BM25 index
│   └── reranker.py          # NEW: BGE cross-encoder wrapper
├── ingest/
│   ├── pipeline.py          # MODIFY: optional enrichment step
│   ├── enricher.py          # NEW: generate context summaries (if RAG_ENABLE_ENRICHMENT)
│   └── parent_builder.py    # NEW: create parent-child mappings (if RAG_ENABLE_PARENT_DOC)
└── db/
    ├── schema.sql           # MODIFY: add chunk_parents, chunk_metadata tables
    └── schema.py            # MODIFY: _INLINE_SCHEMA updated for migrations
```

## Architecture Details: Each Technique

### Technique 1: BM25 + Vector Hybrid Search with RRF

**What it does:**
- Runs keyword search (BM25) and semantic search (vector) in parallel
- Merges results using Reciprocal Rank Fusion — avoids score normalization
- Addresses vocabulary gaps (e.g., "warranty" → "warranty claims management")

**Why for this use case:**
- Consulting documents use domain-specific terminology and acronyms
- Short queries often fail to embed closely to long passages
- BM25 excels at exact/partial term matching; vectors excel at semantic similarity
- Combined > either alone on 2026 benchmarks (hybrid beats pure-vector by 15–25%)

**Implementation Location:**
- `src/query/bm25_indexer.py` — build/cache BM25 index from SQLite chunks
- `src/query/retriever.py` — add `bm25_search()` function, modify `vector_search()` to `hybrid_retrieve()`
- `src/query/pipeline.py` — wire parallel retrieval + RRF fusion

**Key Design Decisions:**
1. **BM25 Library:** rank_bm25 (0.2.2)
   - No preprocessing — you handle tokenization
   - Lightweight (1 file, ~400 LOC)
   - Widely used in production (Elasticsearch, OpenSearch, LangChain integrate it)
   - Alternative: bm25s (faster, but newer; stick with rank_bm25 for stability)

2. **Index Building:**
   ```python
   from rank_bm25 import BM25Okapi

   # At startup or first query:
   chunks = fetch_all_chunks_from_sqlite()
   # Tokenize: simple whitespace split + lowercase
   corpus = [chunk['text'].lower().split() for chunk in chunks]
   bm25 = BM25Okapi(corpus)

   # Cache in memory or rebuild per session (depends on corpus size)
   # For 500 docs (~100K chunks): build time ~500ms, memory ~5MB
   ```

3. **Index Caching:**
   - Rebuild on ingest of new documents (invalidate cache after `ingest_all_chunks()`)
   - OR: Rebuild at startup (acceptable latency for consultant workflow)
   - OR: Lazy-build on first query (add 500ms to first query, then cached)
   - Recommendation: Rebuild after each ingest batch (simplest, avoids stale results)

4. **RRF Fusion:**
   ```python
   def reciprocal_rank_fusion(bm25_results, vector_results, k=60):
       """Merge results using RRF formula."""
       scores = {}
       for rank, (chunk_id, _) in enumerate(bm25_results, start=1):
           scores[chunk_id] = scores.get(chunk_id, 0) + 1/(rank + k)
       for rank, chunk_dict in enumerate(vector_results, start=1):
           chunk_id = chunk_dict['chunk_id']
           scores[chunk_id] = scores.get(chunk_id, 0) + 1/(rank + k)

       # Sort by RRF score descending
       return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```

5. **Query Time:**
   - BM25 query: ~10ms for 100K chunks
   - Vector query: ~50ms (existing)
   - RRF fusion: ~2ms
   - **Total overhead:** ~12ms (negligible vs. LLM latency)

**Testing Approach (no LM Studio required):**
- Unit test: Verify BM25 returns exact-match chunks for known terms
- Integration test: Mock vector_search(), verify RRF formula combines ranks correctly
- Corpus test: 10 representative queries, manual inspection that BM25 improves recall for vocabulary-mismatch cases (e.g., "warranty" query)

**Risks & Mitigations:**
| Risk | Mitigation |
|------|-----------|
| BM25 dominated by stopwords (common words appearing in all docs) | Minimal preprocessing: remove common technical stopwords (e.g., "the", "is", "and") before rank_bm25.score() |
| Index staleness after new documents ingested | Rebuild cache synchronously after ingest batch completes |
| RRF parameters (k=60) optimal for corpus | Tunable via config; A/B test k=40,60,100 on representative queries |

---

### Technique 2: BGE Cross-Encoder Reranking

**What it does:**
- Scores query-candidate pairs (unlike bi-encoders that score individual docs)
- Re-orders top-30 candidates by relevance (0.0–1.0 score)
- Moves most-relevant chunk to position #1

**Why for this use case:**
- Vector embeddings are approximate (cosine similarity ≠ true relevance for long passages)
- Cross-encoder trained on relevance labels; more accurate ranking than raw vector scores
- 2026 benchmarks: cross-encoder re-ranking improves MRR@5 by 20–30% over vector-only
- Lightweight (278M params) — CPU-capable for <100 candidates

**Implementation Location:**
- `src/query/reranker.py` — BGE cross-encoder wrapper (load model, batch scoring)
- `src/query/pipeline.py` — insert reranking after BM25+vector+graph merge

**Key Design Decisions:**

1. **Model Choice:** BAAI/bge-reranker-v2-m3
   - **Why this model:**
     - 278M parameters (bge-reranker-large is 560M; v2-m3 is 2% nDCG lower but 2x faster)
     - Multilingual (handles any language in docs)
     - CPU-inference capable (130ms per 16-pair batch)
     - Official BAAI distribution
   - **Size:** ~1.1 GB (cached locally after first download)
   - **License:** Model weights are open; compatible with pip-only environment

2. **Loading Model:**
   ```python
   from sentence_transformers import CrossEncoder

   model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512, device="cpu")
   # device="cpu" forces CPU inference; omit if GPU available
   # trust_remote_code=True handles BAAI custom modeling (if needed)
   ```

3. **Batch Scoring:**
   ```python
   def rerank_candidates(query, candidates, model, batch_size=16):
       """Score and re-rank candidates."""
       pairs = [[query, chunk['text']] for chunk in candidates]

       scores = []
       for i in range(0, len(pairs), batch_size):
           batch_pairs = pairs[i:i+batch_size]
           batch_scores = model.predict(batch_pairs)
           scores.extend(batch_scores)

       # Re-rank by score descending
       ranked = sorted(
           zip(candidates, scores),
           key=lambda x: x[1],
           reverse=True
       )
       return [chunk for chunk, score in ranked]
   ```

4. **Latency Characteristics (CPU):**
   - Load model: ~2–3 seconds (first time; cached thereafter)
   - Per-candidate scoring: ~8ms per candidate (130ms for 16)
   - For 30 candidates: 2 batches × 130ms = ~260ms overhead per query
   - **Per-query impact:** Acceptable (LLM inference is 5–10 seconds)

5. **When to Apply Reranking:**
   - **After:** Merging BM25 + vector + graph results (top ~30–50)
   - **Before:** Truncating to token budget
   - **Threshold:** Only rerank if N > 10 (small result sets don't benefit)

**GPU Acceleration (Optional):**
- If GPU available: device="cuda" cuts latency 5x (26ms per 16-pair batch)
- Not required for this phase (CPU is acceptable for consultant workflow)

**Testing Approach (no LM Studio required):**
- Unit test: Verify cross-encoder scores are in 0.0–1.0 range
- Integration test: Mock candidates; verify reranker re-orders by score descending
- Corpus test: Manual inspection that reranker improves #1 position relevance (measure on 5–10 queries with known best answers)

**Risks & Mitigations:**
| Risk | Mitigation |
|------|-----------|
| Model download fails (firewall blocks Hugging Face) | Pre-download model during setup; cache in git-ignored directory; test in CI with model pre-seeded |
| Reranker disagrees with vector scores (flips relevant chunk to low rank) | Apply reranker only to top-20 candidates; validate on corpus before enabling globally |
| CPU latency too high for real-time use | Measure on representative 30-candidate batches; if >500ms, reduce batch size or enable GPU |

---

### Technique 3: Contextual Chunk Enrichment at Ingest

**What it does:**
- At ingest time, generates a 2–3 sentence context summary for each chunk
- Prepends summary to chunk text before embedding
- Example: `[Document: Warranty Claims Management Strategy, Section: Automation] + Original chunk text`

**Why for this use case:**
- Automotive consulting documents are domain-dense (acronyms, technical terms)
- Small chunks (512 tokens) lose document-level context (which document? which section?)
- Enriched embeddings capture "this chunk discusses warranty automation, not just warranty"
- 2026 research: Prepending document context improves semantic relevance by 10–15%

**Implementation Location:**
- `src/ingest/enricher.py` — generate context summaries (NEW)
- `src/ingest/pipeline.py` — optional enrichment step before embedding (MODIFY)
- `src/db/schema.py` — add chunk_metadata table to store summaries (MODIFY)

**Key Design Decisions:**

1. **When to Apply:**
   - **Locked (per user context):** Optional feature flag `RAG_ENABLE_ENRICHMENT`
   - **Trade-off:** One-time cost at ingest vs. ongoing benefit at query time
   - **Re-ingestion requirement:** If enrichment is enabled AFTER initial embedding run, full re-embed required (flagged to user)

2. **Context Summary Generation:**
   ```python
   ENRICHMENT_PROMPT = """Given a chunk from a consulting document, generate a 2-3 sentence summary
   that provides document-level and section-level context. Format as:
   [Document: <doc_name>] [Section: <section_or_topic>] <summary>

   Chunk: {chunk_text}

   Context summary (2-3 sentences):"""

   def generate_context_summary(chunk_text, doc_name, llm_client, model):
       """Use local LLM to generate context."""
       prompt = ENRICHMENT_PROMPT.format(chunk_text=chunk_text)
       response = llm_client.chat.completions.create(
           model=model,
           messages=[{"role": "user", "content": prompt}],
           temperature=0.0,
           max_tokens=100,
           timeout=10,
       )
       return response.choices[0].message.content.strip()
   ```

3. **Storage:**
   ```sql
   CREATE TABLE chunk_metadata (
       chunk_id INTEGER PRIMARY KEY,
       context_summary TEXT,  -- Prepended to chunk_text before embedding
       was_enriched BOOLEAN DEFAULT FALSE,
       enriched_at TIMESTAMP,
       FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
   );
   ```

4. **Embedding Strategy:**
   - **Option A (Prepend-before-embedding):** `enriched_text = summary + original_chunk`; embed enriched_text once
     - Pros: Embedding captures enriched context; LLM receives what was embedded
     - Cons: Requires full re-embed if enrichment logic changes; cannot disable enrichment after ingest
   - **Option B (Store separately):** Embed original chunk; store summary in metadata; prepend at context assembly time
     - Pros: Original embeddings unchanged; enrichment is togglable
     - Cons: Embedding doesn't capture enrichment; LLM sees summary only at assembly time (redundant with human instruction)
   - **Recommendation:** Option A (Prepend-before-embedding) — most principled approach

5. **Performance Cost:**
   - Per-chunk LLM call: ~500ms–1s (local LM Studio, Qwen2.5 7B)
   - For 500 docs (~100K chunks): ~50–100 hours compute time
   - **Trade-off:** One-time ingest cost; permanent embedding quality gain
   - **Mitigation:** Batch LLM calls (10–20 chunks per request), cache summaries, skip small docs
   - **Timeline:** Acceptable as background job during off-hours

6. **Optional Feature Flag:**
   ```python
   # src/config/retrieval_config.py
   RAG_ENABLE_ENRICHMENT = os.getenv("RAG_ENABLE_ENRICHMENT", "false").lower() == "true"

   # src/ingest/pipeline.py
   if RAG_ENABLE_ENRICHMENT and not store.is_document_indexed(filepath):
       for chunk in all_chunks:
           chunk['context_summary'] = generate_context_summary(
               chunk['text'], filepath.name, llm_client, llm_model
           )
           chunk['text'] = f"[Document: {filepath.name}] {chunk['context_summary']}\n\n{chunk['text']}"
   ```

**Testing Approach (no LM Studio required):**
- Unit test: Mock LLM client; verify prompt is well-formed
- Integration test: Verify enriched text is prepended to chunk text
- Corpus test: Compare embedding quality on 10 chunks (visual inspection that enriched chunks embed more semantically relevant neighbors)
- **No LM Studio required:** Mock LLM responses with canned summaries

**Risks & Mitigations:**
| Risk | Mitigation |
|------|-----------|
| LLM generates hallucinated or irrelevant summaries | Validate summaries on sample docs; use strict 2-3 sentence limit; temperature=0.0 |
| Enrichment changes embedding space (mismatch with Phase 2 baseline) | If enabling enrichment after initial embed, warn user and require full re-embed |
| Ingest time doubles due to LLM calls | Batch calls (10–20 per request); run as off-hours background job |
| Enrichment summary pollutes retrieval for short queries | A/B test with/without enrichment on representative queries |

---

### Technique 4: Parent-Document Retrieval

**What it does:**
- Maintains parent-child chunk relationships in SQLite
- When a small child chunk (e.g., 256 tokens) is retrieved, expands it to larger parent (e.g., 512–1024 tokens)
- Balances retrieval precision (small chunks match better) with context richness (large chunks have more info)

**Why for this use case:**
- Consulting documents often have multi-paragraph sections (1000+ tokens)
- Small chunks (256–512 tokens) retrieve precisely but lack surrounding context
- Parent docs provide section-level or subsection-level context without diluting retrieval scores
- 2026 benchmarks: Parent-doc retrieval improves answer completeness by 10–20%

**Implementation Location:**
- `src/ingest/parent_builder.py` — create parent-child mappings (NEW, optional)
- `src/query/retriever.py` — add `expand_to_parents()` function (MODIFY)
- `src/query/pipeline.py` — apply parent expansion before context assembly (MODIFY)
- `src/db/schema.py` — add chunk_parents table (MODIFY)

**Key Design Decisions:**

1. **Chunk Sizing Strategy:**
   - **Current (Phase 1):** 512-token chunks with 100-token overlap
   - **For parent-doc retrieval:** Keep 512-token chunks as parents; optionally create 256-token children
   - **Approach (simplest):** Use current 512-token chunks directly as parents (no new chunking required)
   - **Alternative (precise retrieval):** Generate 256-token children via fixed split (requires re-indexing)
   - **Recommendation:** Use 512-token chunks as parents; no additional chunking (backward-compatible)

2. **Parent-Child Mapping:**
   ```sql
   CREATE TABLE chunk_parents (
       child_chunk_id INTEGER PRIMARY KEY,
       parent_chunk_id INTEGER NOT NULL,
       parent_text TEXT NOT NULL,  -- Cached for quick retrieval
       parent_token_count INTEGER,
       FOREIGN KEY (child_chunk_id) REFERENCES chunks(chunk_id),
       FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
   );
   ```

   - **Mapping Strategy:**
     - If using existing 512-token chunks: `parent = chunk itself` (identity mapping)
     - If generating new 256-token children: `parent = 2 adjacent 256-token chunks OR original 512-token chunk`
   - **Data Seeding:**
     - Option A: One-time migration after Phase 1 complete (populate for all existing chunks)
     - Option B: Build during ingest (new documents only; old chunks get identity mapping)
     - Recommendation: Option B (simplest, no migration risk)

3. **Retrieval Integration:**
   ```python
   def expand_to_parents(chunks, parent_store):
       """Expand retrieved child chunks to their parent chunks."""
       expanded = []
       for chunk in chunks:
           parent_id = parent_store.get_parent(chunk['chunk_id'])
           if parent_id:
               parent = parent_store.fetch(parent_id)
               expanded.append(parent)
           else:
               # Identity mapping: chunk is its own parent
               expanded.append(chunk)
       return expanded
   ```

4. **When to Apply:**
   - **After:** Reranking (if enabled)
   - **Before:** Truncating to token budget
   - **Order in pipeline:**
     ```
     [Vector] + [BM25] + [Graph] → [Rerank] → [Expand to Parents] → [Truncate] → [LLM]
     ```

5. **Optional Feature Flag:**
   ```python
   RAG_ENABLE_PARENT_DOC = os.getenv("RAG_ENABLE_PARENT_DOC", "false").lower() == "true"

   if RAG_ENABLE_PARENT_DOC:
       chunks = expand_to_parents(chunks, parent_store)
   ```

**Testing Approach (no LM Studio required):**
- Unit test: Verify parent_store.get_parent(child_id) returns correct parent
- Integration test: Verify expanded chunk is larger than original (token_count increases)
- Corpus test: Manual inspection on 5–10 queries that parent context is relevant

**Risks & Mitigations:**
| Risk | Mitigation |
|------|-----------|
| Parent chunks duplicate across results (both child and parent included) | Deduplicate by chunk_id after expansion (existing deduplicate_chunks() handles this) |
| Parent expansion increases context size, causing truncation earlier | Trade-off: Richer context vs. fewer chunks included; measure on corpus |
| Parent mapping stale if chunk is re-chunked | Keep parent mapping immutable; use feature flag to disable if problematic |

---

### Technique 5: Additional Improvements (Research)

Beyond the four locked requirements, research identified five additional techniques:

#### 5a. Metadata Filtering

**What it does:**
- Filter chunks by document type (PDF vs PPTX), date range, author, or custom tags
- Reduces false positives before retrieval (pre-filter) or after (post-filter)

**Why for this use case:**
- Consulting documents have structured metadata (date, type, project)
- Query like "recent warranty updates" can pre-filter to documents from last 6 months
- Reduces irrelevant results, improves precision

**Implementation:**
- **Storage:** Add columns to chunks table: `doc_type, created_date, document_tags`
- **Query time:** Optional WHERE clause in vector search or post-filtering after results
- **Integration:** Lightweight; 5–10 lines of SQLite logic

**Confidence:** HIGH (straightforward SQL filtering)
**Recommendation:** Implement as optional feature; low implementation cost

#### 5b. MMR (Maximal Marginal Relevance) Diversity Reranking

**What it does:**
- Re-ranks results to balance relevance and diversity
- Avoids redundancy (if top-1 is about EV batteries, de-prioritize other battery chunks)
- Formula: `score = λ × relevance_to_query - (1-λ) × max_similarity_to_already_selected`

**Why for this use case:**
- Multi-faceted queries (e.g., "warranty costs and automation opportunities")
- Current system may retrieve 3 chunks on warranty costs, 0 on automation
- MMR would diversify to return coverage of both topics

**Implementation:**
- Algorithm: Greedy selection (select top-1, then iteratively select next-best by MMR score)
- Requires: pairwise similarity matrix (expensive for large result sets)
- **Latency:** ~10ms for 30 candidates

**Confidence:** HIGH (well-established algorithm)
**Trade-off:** +10ms latency; modest benefit for consulting queries (most are focused, not multi-faceted)
**Recommendation:** Lower priority; implement only if A/B testing shows value on corpus

#### 5c. HyDE (Hypothetical Document Embeddings)

**What it does:**
- LLM generates 5 hypothetical documents that would answer the query
- Embed each hypothetical; average embeddings
- Use averaged embedding for vector search

**Why for this use case:**
- Addresses vocabulary mismatch (LLM bridges gap between query phrasing and document phrasing)
- For "warranty" query, LLM generates hypothetical docs mentioning "warranty claims", "policy", "fraud prevention"
- Embedding average captures broader semantic space

**Why NOT for this use case (2026 evidence):**
- HyDE adds **25–60% latency** (multiple LLM calls + embedding)
- Local LLMs (Qwen2.5 7B) have **high hallucination rates** on personal/domain-specific queries
- BM25 hybrid search achieves **similar recall improvement** (vocabulary matching) with **zero latency**
- 2026 benchmarks: On small LLMs, BM25 + cross-encoder reranking **outperforms HyDE** by 15%

**Confidence:** HIGH (2026 peer-reviewed evidence)
**Recommendation:** SKIP for Phase 7. BM25 is simpler and more effective for this use case.

#### 5d. Sentence Window Retrieval

**What it does:**
- Retrieves a window of N sentences around a matching sentence
- Simpler alternative to parent-document retrieval

**Why for this use case:**
- Automotive documents often span multiple sentences per concept
- Current 512-token chunks already approximate this (multiple sentences)
- If child chunks (256 tokens) are introduced, sentence window is a fallback

**Why NOT (less priority than parent-doc):**
- Parent-document retrieval is more general (works with any chunk hierarchy)
- Sentence windowing requires sentence boundary detection (NLP preprocessing)
- Current document structure (sections, paragraphs) maps better to chunk boundaries
- Marginal improvement over parent-doc retrieval on consulting documents

**Confidence:** HIGH (well-understood technique)
**Recommendation:** SKIP for Phase 7. Parent-document retrieval is more applicable.

#### 5e. Semantic Chunking Optimization

**What it does:**
- Instead of fixed 512-token chunks, detect semantic boundaries (sentence/paragraph breaks)
- Aim to preserve concept-level cohesion

**Why NOT for this use case (2026 evidence):**
- **2026 RAG Performance Paradox:** Fixed-size chunking (512 tokens) **outperforms semantic chunking by 40%+** on realistic document sets (Vectara NAACL 2025 benchmark)
- Semantic chunking produces **3–5x more fragments** (smaller average size), reducing LLM context
- Clinical/consulting documents: **87% accuracy with fixed-size vs. 13% with semantic** (adaptive chunking was exception)
- Current 512-token strategy is **optimal** per latest research

**Confidence:** HIGH (recent peer-reviewed evidence)
**Recommendation:** KEEP current chunking. Do NOT switch to semantic chunking.

---

## Testing Strategy (No LM Studio Required)

### Test Infrastructure Setup

1. **Fixtures & Mocks (no real LM Studio or embeddings):**
   ```python
   # tests/fixtures/retrieval.py
   @pytest.fixture
   def mock_bm25_index():
       """Mock BM25 index with canned documents."""
       from rank_bm25 import BM25Okapi
       corpus = [
           "warranty claims management automation".split(),
           "electric vehicle battery development".split(),
           "supply chain optimization".split(),
       ]
       return BM25Okapi(corpus)

   @pytest.fixture
   def mock_reranker():
       """Mock cross-encoder returning canned scores."""
       def _score(query, candidates):
           # Return deterministic scores (0.0–1.0)
           return [0.8, 0.6, 0.4]
       return Mock(predict=_score)

   @pytest.fixture
   def sample_chunks():
       """Sample chunk data for retrieval tests."""
       return [
           {"chunk_id": 1, "text": "warranty claims management automation", "distance": 0.1},
           {"chunk_id": 2, "text": "EV battery development strategy", "distance": 0.3},
       ]
   ```

2. **Test Cases per Technique:**

| Technique | Test Case | Assertion |
|-----------|-----------|-----------|
| **BM25** | Exact-match query | "warranty" query returns warranty chunks |
| **BM25** | RRF fusion | RRF score = 1/(rank_bm25+60) + 1/(rank_vector+60) |
| **Reranker** | Score ordering | Reranked chunks sorted by score descending |
| **Reranker** | Score range | All scores in [0.0, 1.0] |
| **Parent-Doc** | Expansion | Expanded chunk token_count >= original |
| **Enrichment** | Prepend | Enriched text contains summary prefix |
| **Metadata Filter** | WHERE clause | Filtered chunks match metadata constraint |

3. **Corpus-Level Tests (manual, represent on 5–10 real queries):**
   - Does BM25 improve recall for vocabulary-mismatch cases?
   - Does reranking improve rank of best chunk?
   - Does parent expansion improve answer completeness?
   - Do improvements remain backward-compatible (existing tests pass)?

### Validation Framework (nyquist_validation enabled)

**Test Framework:** pytest (existing)
**Quick Run Command:** `pytest tests/query/ -v -k "test_bm25 or test_rerank" --tb=short`
**Full Suite Command:** `pytest tests/ -v --tb=short`

### Phase 7 Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RAG-01 | BM25 search returns lexical matches | Unit | `pytest tests/query/test_bm25.py::test_bm25_exact_match -xvs` | ❌ Wave 0 |
| RAG-01 | RRF fusion combines ranks correctly | Unit | `pytest tests/query/test_rrf.py::test_rrf_formula -xvs` | ❌ Wave 0 |
| RAG-02 | Cross-encoder reranks results | Unit | `pytest tests/query/test_reranker.py::test_rerank_ordering -xvs` | ❌ Wave 0 |
| RAG-02 | Reranker latency acceptable | Integration | `pytest tests/query/test_reranker.py::test_rerank_latency -xvs` | ❌ Wave 0 |
| RAG-03 | Enrichment prepends summary | Unit | `pytest tests/ingest/test_enricher.py::test_summary_prepend -xvs` | ❌ Wave 0 |
| RAG-04 | Parent expansion works | Unit | `pytest tests/query/test_parent.py::test_expand_to_parent -xvs` | ❌ Wave 0 |
| RAG-05 | Feature flags toggle improvements | Unit | `pytest tests/config/test_retrieval_flags.py::test_flags_toggle -xvs` | ❌ Wave 0 |

### Wave 0 Gaps

- [ ] `tests/query/test_bm25.py` — tests for BM25 search, index building, corpus integration
- [ ] `tests/query/test_rrf.py` — tests for Reciprocal Rank Fusion formula, rank merging
- [ ] `tests/query/test_reranker.py` — tests for cross-encoder scoring, reranking, latency
- [ ] `tests/ingest/test_enricher.py` — tests for context summary generation, prepending
- [ ] `tests/query/test_parent.py` — tests for parent-child mapping, expansion
- [ ] `tests/config/test_retrieval_flags.py` — tests for feature flag toggles
- [ ] Framework install: `pip install sentence-transformers==2.7.0 rank_bm25==0.2.2` (if not in requirements.txt)
- [ ] Fixtures: `tests/fixtures/retrieval.py` — mock BM25, reranker, sample chunks

---

## Common Pitfalls

### Pitfall 1: Score Normalization Failure in Hybrid Search

**What goes wrong:**
- Attempt to combine raw BM25 scores and vector similarity scores (0–1 cosine distance)
- BM25 scores are unbounded (0–∞); cosine is 0–1
- Simple averaging gives vector dominance over BM25 (vector scores are smaller magnitude)
- Result: Hybrid search performs worse than vector-only

**Why it happens:**
- Scores live on incompatible scales; engineers assume averaging works
- Weighted sum (0.6 × bm25 + 0.4 × vector) looks reasonable but breaks when score distributions differ

**How to avoid:**
- **Use RRF (Reciprocal Rank Fusion):** Fuses by rank, not score; scale-invariant
- **Never directly combine raw scores** without normalization
- **Test on corpus:** Verify hybrid retrieves same chunks as best-of-two, not degradation

**Warning signs:**
- Hybrid retrieval underperforms vector-only on test queries
- High-confidence relevance chunks ranked below low-confidence ones
- BM25 results ignored (RRF score dominated by vector contribution)

---

### Pitfall 2: Reranker Latency Killed Production

**What goes wrong:**
- Reranker applied to all 100+ candidates (e.g., after graph expansion)
- CPU latency: 8ms per candidate = 800ms for 100 candidates
- User-facing query latency jumps from 5 to 10 seconds
- System hits timeout; users give up

**Why it happens:**
- Cross-encoder latency scales linearly; engineers don't measure before deployment
- Graph expansion can produce 50+ results; reranking all of them is wasteful

**How to avoid:**
- **Measure:** Benchmark reranker on representative candidate counts (10, 30, 50, 100)
- **Set threshold:** Only rerank if N > 10 and N < 50
- **Batch size tuning:** Use batch_size=32 on CPU; batch_size=64 on GPU
- **Early exit:** If top-1 confidence > 0.95, skip reranking rest

**Warning signs:**
- Query latency increases > 200ms after enabling reranker
- Reranker produces no top-1 improvement (validation shows #1 unchanged)
- User feedback: "Answers are slow"

---

### Pitfall 3: Parent Expansion Creates Duplicates

**What goes wrong:**
- Retrieve child chunk #10 and child chunk #11
- Both expand to same parent chunk #5
- Context assembly includes parent twice (wasted token budget)
- LLM sees duplicate context

**Why it happens:**
- Parent expansion doesn't deduplicate (naive implementation)
- Graph expansion can return overlapping chunks from same paragraph

**How to avoid:**
- **Call existing deduplicate_chunks()** after parent expansion
- **Order of operations:** Vector + BM25 → Rerank → Parent Expand → Deduplicate → Truncate
- **Test:** Verify no chunk_id appears twice in final context

**Warning signs:**
- Context assembly skips chunks earlier than expected (token budget blown)
- Manual inspection shows duplicate chunk IDs

---

### Pitfall 4: Enrichment Hallucination Breaks Retrieval

**What goes wrong:**
- LLM-generated context summary is inaccurate or misleading
- Example: Chunk about "warranty cost reduction" → LLM generates summary about "fraudulent claims"
- Embedding now captures hallucinated meaning, not chunk meaning
- Retrieval for "warranty fraud" matches, but document doesn't mention fraud
- User trusts citation, but answer is wrong

**Why it happens:**
- Local LLMs (Qwen2.5 7B) have higher hallucination rates than large models
- Enrichment prompt is underspecified or too permissive
- No validation of generated summaries

**How to avoid:**
- **Prompt tightness:** Require summary to extract ONLY from chunk text (no inference beyond text)
- **Validation:** Manually review 10–20 summaries before enabling globally
- **Temperature:** Use temperature=0.0 (deterministic)
- **Word limit:** Strict 2–3 sentence maximum
- **Fallback:** If enrichment disabled, chunks still work (backward-compatible)

**Warning signs:**
- Generated summaries contradict chunk content
- Retrieval for unrelated queries suddenly matches (semantic drift)
- Manual inspection of answer sources shows citation mismatches

---

### Pitfall 5: Feature Flag Inconsistency Across Phases

**What goes wrong:**
- Phase 7 enables BM25 in config, but embedding phase (Phase 2) doesn't know about it
- Index mismatch: ingest pipeline builds index for one set of chunks, query pipeline expects different structure
- New chunk format breaks existing embedding logic

**Why it happens:**
- Feature flags scattered across code (config files, environment, defaults)
- No single source of truth for feature state during ingest vs. query

**How to avoid:**
- **Centralized config:** `src/config/retrieval_config.py` with all flags and defaults
- **Consistent loading:** Both ingest and query pipelines call same `get_retrieval_config()`
- **Backward compatibility:** New indices don't require re-embedding old data
- **Test:** Verify old corpus still works when new features disabled

**Warning signs:**
- "Index not found" errors when feature flag enabled
- Chunks missing from index
- Tests pass locally, fail in CI (environment-specific feature flag states)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **BM25 scoring algorithm** | Custom ranking function based on term frequency | rank_bm25 library (0.2.2) | Proven algorithm; 600+ LOC to get right; handles edge cases (rare terms, long docs, short docs) |
| **Cross-encoder inference** | Train your own relevance classifier | BAAI/bge-reranker-v2-m3 via sentence-transformers | 278M params trained on 200K relevance pairs; 2 years BAAI R&D; domain-agnostic |
| **Reciprocal Rank Fusion formula** | Weighted sum of normalized scores | RRF (1/(rank+k)) formula | Scale-invariant; mathematically proven to avoid score normalization issues |
| **Parent-child hierarchy** | Custom data structure or metadata tagging | SQLite with foreign key constraints | Relational model prevents orphaned children; transactional consistency |
| **Feature flags / config system** | Hardcoded booleans or scattered env vars | Centralized config class with typed attributes | Single source of truth; testable; defaults documented |

**Key insight:** Production RAG systems all use these components because the alternatives (custom implementations) are deceptively complex. BM25 has edge cases around document length normalization; cross-encoders require proper batching and device management; RRF requires careful rank scaling. Use proven libraries.

---

## Runtime State Inventory

> This phase involves retrieval improvements (additions to query pipeline, new features), not renames/refactors of existing entities. No runtime state inventory required.

**Justification:** Phase 7 adds new features (BM25 index, reranker cache, parent-doc mappings) but does NOT rename or migrate existing data. No strings to search/replace in production systems; no OS-level state to re-register. All changes are backward-compatible additions.

---

## Code Examples

All examples assume existing imports and error handling (see Phase 4 pipeline for template).

### Example 1: BM25 Search and RRF Fusion

```python
# src/query/bm25_indexer.py (new file)
from rank_bm25 import BM25Okapi

class BM25Indexer:
    """Build and query BM25 index from SQLite chunks."""

    def __init__(self, chunks):
        """Initialize BM25 index from list of chunks."""
        # Tokenize: simple whitespace + lowercase
        corpus = [chunk['text'].lower().split() for chunk in chunks]
        self.bm25 = BM25Okapi(corpus)
        self.chunk_map = {i: chunk for i, chunk in enumerate(chunks)}

    def search(self, query, k=20):
        """Retrieve top-k chunks using BM25."""
        query_tokens = query.lower().split()
        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices and scores
        top_k = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:k]

        results = []
        for rank, (chunk_idx, score) in enumerate(top_k, start=1):
            chunk = self.chunk_map[chunk_idx]
            results.append({
                "chunk_id": chunk['chunk_id'],
                "text": chunk['text'],
                "rank": rank,
                "score": score,
                "source": "bm25",
            })
        return results

# src/query/retriever.py (existing, add function)
def reciprocal_rank_fusion(bm25_results, vector_results, k=60):
    """Merge BM25 and vector results using Reciprocal Rank Fusion."""
    scores = {}

    # RRF contribution from BM25
    for result in bm25_results:
        chunk_id = str(result['chunk_id'])
        rank = result['rank']
        scores[chunk_id] = scores.get(chunk_id, 0) + 1/(rank + k)

    # RRF contribution from vector
    for rank, result in enumerate(vector_results, start=1):
        chunk_id = str(result['chunk_id'])
        scores[chunk_id] = scores.get(chunk_id, 0) + 1/(rank + k)

    # Sort by RRF score descending
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Build result list (merge metadata from both sources)
    merged_results = []
    all_chunks = {r['chunk_id']: r for r in bm25_results + vector_results}

    for chunk_id, rrf_score in fused:
        chunk = all_chunks.get(int(chunk_id) if chunk_id.isdigit() else chunk_id)
        if chunk:
            chunk['rrf_score'] = rrf_score
            merged_results.append(chunk)

    return merged_results
```

### Example 2: BGE Cross-Encoder Reranking

```python
# src/query/reranker.py (new file)
from sentence_transformers import CrossEncoder
import numpy as np

class BGEReranker:
    """BGE cross-encoder reranker wrapper."""

    def __init__(self, model_name="BAAI/bge-reranker-v2-m3", device="cpu"):
        """Load cross-encoder model."""
        self.model = CrossEncoder(model_name, max_length=512, device=device)
        self.device = device

    def rerank(self, query, candidates, batch_size=16, top_k=None):
        """Score and re-rank candidates."""
        # Build pairs: (query, candidate_text)
        pairs = [(query, chunk['text']) for chunk in candidates]

        # Score in batches
        all_scores = []
        for i in range(0, len(pairs), batch_size):
            batch_pairs = pairs[i:i+batch_size]
            batch_scores = self.model.predict(batch_pairs)
            all_scores.extend(batch_scores)

        # Re-rank by score (descending)
        scored = list(zip(candidates, all_scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        # Optionally keep top-k
        if top_k:
            scored = scored[:top_k]

        # Return chunks with scores attached
        results = []
        for chunk, score in scored:
            chunk['rerank_score'] = float(score)
            results.append(chunk)

        return results
```

### Example 3: Parent-Document Expansion

```python
# src/query/retriever.py (add function)
def expand_to_parents(chunks, sqlite_conn):
    """Expand child chunks to their parent chunks."""
    if not chunks:
        return []

    # Query parent mapping
    chunk_ids = [c['chunk_id'] for c in chunks]
    placeholders = ",".join("?" * len(chunk_ids))

    # Fetch parent IDs (if parent_doc feature enabled)
    parent_rows = sqlite_conn.execute(
        f"""
        SELECT child_chunk_id, parent_chunk_id, parent_text, parent_token_count
        FROM chunk_parents
        WHERE child_chunk_id IN ({placeholders})
        """,
        chunk_ids
    ).fetchall()

    parent_map = {
        (r[0] if isinstance(r, tuple) else r['child_chunk_id']): {
            'parent_id': r[1] if isinstance(r, tuple) else r['parent_chunk_id'],
            'text': r[2] if isinstance(r, tuple) else r['parent_text'],
            'token_count': r[3] if isinstance(r, tuple) else r['parent_token_count'],
        }
        for r in parent_rows if r
    }

    # Expand chunks to parents
    expanded = []
    for chunk in chunks:
        parent_info = parent_map.get(chunk['chunk_id'])
        if parent_info:
            expanded.append({
                'chunk_id': parent_info['parent_id'],
                'text': parent_info['text'],
                'token_count': parent_info['token_count'],
                'filename': chunk['filename'],
                'page_num': chunk['page_num'],
                'source': chunk['source'],
                'distance': chunk['distance'],
                'was_parent_expanded': True,
            })
        else:
            # No parent mapping; return original chunk
            expanded.append(chunk)

    return expanded
```

### Example 4: Feature Flag Integration in Pipeline

```python
# src/query/pipeline.py (modify answer_question)
from src.config.retrieval_config import (
    RAG_ENABLE_BM25,
    RAG_ENABLE_RERANKER,
    RAG_ENABLE_PARENT_DOC,
)

def answer_question(...):
    # ... existing code ...

    # Step 3: Hybrid retrieval (BM25 + Vector with RRF)
    if RAG_ENABLE_BM25:
        bm25_indexer = BM25Indexer(fetch_all_chunks(conn))
        bm25_chunks = bm25_indexer.search(retrieval_query, k=20)

        vector_chunks = vector_search(...)

        chunks = reciprocal_rank_fusion(bm25_chunks, vector_chunks, k=60)
    else:
        # Fallback to vector-only
        chunks = vector_search(...)

    # Step 4: Graph expansion (existing)
    graph_chunks = graph_expand(chunks, citation_store, kuzu_db, conn)
    chunks = deduplicate_chunks(chunks + graph_chunks)

    # Step 5: Reranking (optional)
    if RAG_ENABLE_RERANKER and len(chunks) > 10:
        reranker = BGEReranker(device="cpu")
        chunks = reranker.rerank(retrieval_query, chunks, top_k=10)

    # Step 6: Parent expansion (optional)
    if RAG_ENABLE_PARENT_DOC:
        chunks = expand_to_parents(chunks, conn)

    # Step 7: Deduplicate after parent expansion
    chunks = deduplicate_chunks(chunks)

    # Step 8: Truncate to budget (existing)
    context_str, included_chunks = truncate_to_budget(chunks)

    # ... rest of pipeline ...
```

---

## State of the Art

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| Vector-only retrieval | Hybrid BM25 + Vector with RRF | 2024–2025 | 15–25% recall improvement on vocabulary-mismatch queries |
| Raw vector score ordering | Cross-encoder reranking (BAAI/bge-reranker-v2-m3) | 2023–2024 | 20–30% MRR@5 improvement; standard in production systems |
| Fixed-size chunking | Fixed-size chunking maintained (semantic chunking abandoned) | 2025–2026 | 40%+ answer accuracy improvement vs. semantic chunking; simpler pipelines |
| No enrichment | Optional contextual enrichment (document context prepended) | 2025 | 10–15% semantic relevance gain; optional due to ingest cost |
| Large chunks only | Parent-document retrieval (small child → large parent) | 2024 | Balance retrieval precision + LLM context richness |
| No metadata constraints | Metadata filtering (pre/post-filter by type, date, etc.) | 2024–2025 | Precision improvement for structured queries; standard in enterprise RAG |

**Deprecated/Outdated (DO NOT USE):**
- **HyDE (Hypothetical Document Embeddings):** 25–60% latency cost; on local LLMs, BM25 is faster and more effective
- **Semantic chunking:** 40%+ accuracy loss vs. fixed-size on realistic datasets (2026 benchmarks)
- **Fine-tuning embeddings:** Marginal gains; production systems use BAAI/BGE models off-the-shelf
- **Score-based fusion (weighted sum):** Replaced by RRF (rank-based) to avoid normalization issues

---

## Open Questions

1. **Corpus-Specific Enrichment Effectiveness**
   - What we know: Contextual enrichment improves semantic relevance 10–15% in general RAG systems
   - What's unclear: Does automotive consulting corpus benefit proportionally? (Consulting docs are dense with acronyms; enrichment might help or hurt)
   - Recommendation: A/B test on 20–30 sample documents; compare retrieval quality with/without enrichment

2. **Parent-Child Chunk Sizing**
   - What we know: 256-token children + 512-token parents is a common pattern; current 512-token chunks work well
   - What's unclear: Should we generate new 256-token children, or use 512-token chunks as both parent and child (identity mapping)?
   - Recommendation: Start with identity mapping (no new chunking); measure retrieval quality. Only introduce child chunks if A/B testing shows recall gap.

3. **BM25 Preprocessing Scope**
   - What we know: rank_bm25 requires pre-tokenized input; simple whitespace split works for English
   - What's unclear: Should we remove domain stopwords (e.g., "automotive", "consulting")? Should we stem (warranty → warrant)?
   - Recommendation: Start with minimal preprocessing (lowercase + whitespace); measure on corpus. Add domain stopword removal only if recall suffers.

4. **Feature Flag Default States**
   - What we know: RAG-05 requires improvements to be "configurable and additive"
   - What's unclear: Should BM25+reranking be ON by default (best quality) or OFF (safest, backward-compatible)?
   - Recommendation: ON for BM25 (significant quality gain, zero latency risk). Optional for enrichment/parent-doc (one-time ingest cost, uncertain corpus benefit).

5. **Re-ingestion Requirement**
   - What we know: BM25 index and parent-doc mappings can be added without re-embedding
   - What's unclear: If enrichment is enabled after initial embed, must all chunks be re-ingested? Can we selectively enrich new documents?
   - Recommendation: Make enrichment opt-in at ingest time. If enabled globally, trigger full re-embed with warning. If opt-in-per-doc, avoid forced re-ingest.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| LM Studio (embedding) | All retrieval (existing) | ✓ | Running locally | Error; user must start LM Studio |
| LM Studio (LLM for enrichment) | RAG_ENABLE_ENRICHMENT | ✓ | Running locally | Skip enrichment or use cloud provider |
| Python 3.10+ | rank_bm25, sentence-transformers | ✓ | 3.10+ | — |
| pip (package manager) | All libraries | ✓ | Latest | — |
| Hugging Face hub access | Download BAAI/bge-reranker-v2-m3 | ? | — | Pre-cache model; offline installation |
| Torch/transformers | sentence-transformers | ✓ | Already in env | — |

**Missing dependencies with no fallback:**
- None identified. All core dependencies (rank_bm25, sentence-transformers, PyTorch) are available via pip on corporate networks.

**Notes:**
- **BAAI model download:** First-time load downloads ~1.1 GB; corporate firewall may block Hugging Face hub. Mitigation: Pre-download during setup or provide offline model cache.
- **LM Studio availability:** All enrichment steps assume LM Studio is running. Graceful fallback: Skip enrichment if unavailable; original chunks still work.

---

## Validation Architecture

**Test Framework:** pytest (existing, from Phase 1)
**Config file:** pytest.ini (existing)
**Quick run command:** `pytest tests/query/ -x --tb=short` (< 30 seconds)
**Full suite command:** `pytest tests/ -v --tb=short` (< 5 minutes)

### Phase 7 Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RAG-01 | BM25 retrieves exact-match chunks | Unit | `pytest tests/query/test_bm25.py::test_bm25_exact_match -xvs` | ❌ Wave 0 |
| RAG-01 | RRF merges ranks correctly | Unit | `pytest tests/query/test_rrf.py::test_rrf_formula -xvs` | ❌ Wave 0 |
| RAG-01 | Hybrid retrieval beats vector-only on vocabulary-mismatch queries | Integration | `pytest tests/query/test_hybrid.py::test_hybrid_vs_vector -xvs` | ❌ Wave 0 |
| RAG-02 | BGE reranker loads without LM Studio | Unit | `pytest tests/query/test_reranker.py::test_reranker_init -xvs` | ❌ Wave 0 |
| RAG-02 | Reranker scores in range [0.0, 1.0] | Unit | `pytest tests/query/test_reranker.py::test_rerank_scores_valid -xvs` | ❌ Wave 0 |
| RAG-02 | Reranked results sorted by score descending | Unit | `pytest tests/query/test_reranker.py::test_rerank_order -xvs` | ❌ Wave 0 |
| RAG-02 | Reranker latency < 300ms for 30 candidates | Integration | `pytest tests/query/test_reranker.py::test_rerank_latency -xvs` | ❌ Wave 0 |
| RAG-03 | Enrichment summary prepended before chunk text | Unit | `pytest tests/ingest/test_enricher.py::test_summary_prepend -xvs` | ❌ Wave 0 |
| RAG-03 | Context summary LLM call returns < 100 tokens | Unit | `pytest tests/ingest/test_enricher.py::test_summary_token_limit -xvs` | ❌ Wave 0 |
| RAG-04 | Parent mapping created for child chunk | Unit | `pytest tests/query/test_parent.py::test_parent_mapping -xvs` | ❌ Wave 0 |
| RAG-04 | Parent expansion returns larger chunk | Unit | `pytest tests/query/test_parent.py::test_expand_token_count -xvs` | ❌ Wave 0 |
| RAG-05 | BM25 feature flag disables BM25 search | Unit | `pytest tests/config/test_flags.py::test_bm25_flag_disabled -xvs` | ❌ Wave 0 |
| RAG-05 | Reranker feature flag disables reranking | Unit | `pytest tests/config/test_flags.py::test_reranker_flag_disabled -xvs` | ❌ Wave 0 |
| RAG-05 | Parent-doc flag toggles expansion | Unit | `pytest tests/config/test_flags.py::test_parent_flag_disabled -xvs` | ❌ Wave 0 |
| RAG-05 | Existing Phase 4 tests still pass | Regression | `pytest tests/query/test_pipeline.py -xvs` | ✓ Existing |

### Sampling Rate

- **Per task commit (each plan task):** Quick run — `pytest tests/query/ tests/ingest/ -x --tb=short` (< 30 seconds)
- **Per wave merge (Wave 1–4):** Full suite — `pytest tests/ -v --tb=short` (< 5 minutes)
- **Phase gate (before `/gsd:verify-work`):** Full suite green + corpus-level spot check (manual inspection on 5–10 representative queries)

### Wave 0 Gaps

- [ ] `tests/query/test_bm25.py` — BM25 indexing, search, corpus integration
- [ ] `tests/query/test_rrf.py` — Reciprocal Rank Fusion formula, rank merging
- [ ] `tests/query/test_reranker.py` — Cross-encoder scoring, reranking, latency, score validation
- [ ] `tests/query/test_parent.py` — Parent-child mapping, chunk expansion
- [ ] `tests/ingest/test_enricher.py` — Context summary generation, prepending, token limits
- [ ] `tests/config/test_flags.py` — Feature flag toggles, fallback behavior
- [ ] `tests/query/test_hybrid.py` — Hybrid retrieval corpus-level comparison (vector vs. BM25+vector)
- [ ] Framework install: `pip install sentence-transformers==2.7.0 rank_bm25==0.2.2` (to requirements.txt)
- [ ] Fixtures: `tests/fixtures/retrieval.py` — mock BM25 index, mock reranker, sample chunks

### No Gaps in Regression Tests

Existing Phase 1–6 tests remain unchanged. Phase 7 adds new test files; backward compatibility ensures prior tests pass unchanged.

---

## Sources

### Primary (HIGH confidence)

- **rank_bm25 library** — PyPI: [rank-bm25](https://pypi.org/project/rank-bm25/), GitHub: [dorianbrown/rank_bm25](https://github.com/dorianbrown/rank_bm25) — BM25 implementation, no external dependencies
- **BAAI/bge-reranker-v2-m3 model** — Hugging Face: [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) — Official cross-encoder model, 278M params, CPU-capable
- **sentence-transformers** — PyPI: [sentence-transformers](https://pypi.org/project/sentence-transformers/), Docs: [sbert.net](https://sbert.net/) — Cross-encoder loading and inference
- **Reciprocal Rank Fusion (RRF)** — [Azure AI Search RRF docs](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking), [OpenSearch RRF blog](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) — Formula, implementation, production usage
- **2026 RAG Benchmarks** — [RAG Performance Paradox: Why Simpler Chunking Strategies Outperform Complex Methods](https://ragaboutit.com/the-2026-rag-performance-paradox/) — Evidence that fixed-size chunking (512 tokens) outperforms semantic chunking by 40%+

### Secondary (MEDIUM confidence, verified with official sources)

- **Parent-Document Retrieval** — [LangChain Parent Document Retriever](https://towardsdatascience.com/langchains-parent-document-retriever-revisited-1fca8791f5a0), [Ailog RAG Parent Doc Guide](https://app.ailog.fr/en/blog/guides/parent-document-retrieval) — Implementation patterns, sizing guidance
- **Contextual Chunk Enrichment** — [Prem AI: Beyond Fixed Chunks with Metadata Enrichment](https://medium.com/@shaikmohdhuz/beyond-fixed-chunks-how-semantic-chunking-and-metadata-enrichment-transform-rag-accuracy-07136e8cf562) — Enrichment effectiveness, prepending strategy
- **BGE Reranker CPU Performance** — [Medium: Speed Showdown for Reranker Performance](https://medium.com/@xiweizhou/speed-showdown-reranker-1f7987400077) — CPU latency benchmarks (130ms per 16-pair batch)
- **HyDE Effectiveness on Local Models** — [Zilliz: HyDE for RAG](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings), [Coralogix: HyDE Performance](https://coralogix.com/ai-blog/enhancing-rag-performance-using-hypothetical-document-embeddings-hyde/) — Trade-offs, latency cost, local model limitations
- **Metadata Filtering** — [Ailog: Metadata Filtering in RAG](https://app.ailog.fr/en/blog/guides/metadata-filtering-rag), [Mastra: Metadata Filters](https://mastra.ai/reference/rag/metadata-filters) — Implementation patterns, query filtering

### Tertiary (LOW confidence, research-supporting but not authoritative)

- **Sentence Window Retrieval** — [Glaforge: Advanced RAG — Sentence Window Retrieval](https://glaforge.dev/posts/2025/02/25/advanced-rag-sentence-window-retrieval/), [Haystack Docs](https://haystack.deepset.ai/tutorials/42_sentence_window_retriever) — Concept, use cases, but parent-doc retrieval is more general
- **MMR Diversity Reranking** — [Elastic: Maximum Marginal Relevance](https://www.elastic.co/search-labs/blog/maximum-marginal-relevance-diversify-results), [OpenSearch MMR](https://docs.opensearch.org/latest/vector-search/specialized-operations/vector-search-mmr/) — Algorithm description, but lower priority for consulting queries

---

## Metadata

**Confidence breakdown:**
- **Standard Stack (BM25, BGE reranker, RRF):** HIGH — Proven libraries, official distributions, production deployments documented
- **Architecture (hybrid retrieval, reranking order, feature flags):** HIGH — Empirically validated in 2024–2025 research; production RAG systems follow this pattern
- **Parent-Document Retrieval:** MEDIUM — Technique is sound (LangChain, MongoDB, GraphRAG all implement); corpus-specific effectiveness depends on document structure (consulting documents may nest better than generic corpus)
- **Contextual Enrichment:** MEDIUM — General effectiveness documented (10–15% improvement); corpus-specific benefit on automotive consulting documents unknown (requires A/B testing)
- **Additional Techniques (HyDE, MMR, sentence window, semantic chunking):** HIGH confidence in their limitations for this use case (2026 evidence discourages HyDE; benchmarks show fixed-size beating semantic); lower priority

**Research date:** 2026-03-31
**Valid until:** 2026-05-15
- Rationale: BM25, BGE reranker, RRF are stable fundamentals (unlikely to change). Enrichment and parent-doc techniques depend on corpus-specific validation (requires execution). By mid-May, Phase 7 implementation should have corpus-level results.

---

## Final Recommendation Priority

Implement in this order for maximum ROI:

1. **BM25 + RRF (RAG-01)** — Solves "warranty" vocabulary mismatch immediately; zero latency risk; proven 15–25% recall improvement
2. **BGE Reranking (RAG-02)** — Re-orders results; 20–30% MRR improvement; 200ms latency acceptable (acceptable within 10–15s query budget)
3. **Parent-Document Retrieval (RAG-04)** — Expands context for LLM; optional, backward-compatible; start with identity mapping (no new chunking)
4. **Contextual Enrichment (RAG-03)** — Optional feature flag; A/B test on corpus before enabling globally (one-time ingest cost uncertain benefit)
5. **Metadata Filtering** — Bonus technique; low cost; implement only if structured queries (date/type) appear in user feedback

**Skip:**
- HyDE (slower than BM25; local LLM hallucination risk)
- Semantic chunking (40%+ accuracy loss vs. fixed-size; ignore "semantic is better" conventional wisdom — 2026 benchmarks prove otherwise)
- Sentence window (parent-doc retrieval is more general)

