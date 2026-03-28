# Feature Landscape: Local GraphRAG Document Intelligence

**Domain:** Enterprise document Q&A system with knowledge graph indexing
**Context:** Automotive consulting archive (15 years, 500–2000 documents: PDFs + PPTXs)
**Research method:** GraphRAG architecture analysis + document intelligence patterns (training data)
**Researched:** 2026-03-28
**Overall confidence:** MEDIUM (no live web access; based on training knowledge through Feb 2025)

---

## Table Stakes

Features users expect. Missing these = product feels incomplete or unusable for the stated use case.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Document ingestion** | Users have 500–2000 documents to index; no ingestion = no data in system | Medium | Handles PDF + PPTX; text extraction only (no OCR/visual embeddings per PROJECT.md) |
| **Text search / keyword retrieval** | Users need basic "find docs mentioning X" as fallback to semantic search | Low | Even semantic systems include BM25 or TF-IDF for exact matches |
| **Semantic search** | Core value: "find similar prior work" requires embedding similarity across document corpus | Medium | Embeddings must run locally (LM Studio OpenAI API); inference cost is high |
| **Chat interface** | Automotive consultants are non-technical; chat UX is required for adoption | Low | Web-based chat history + query input; local model inference |
| **Source citations** | Consultants must verify answers are grounded; bare answers are worthless | Low | Return document + chunk references with retrieved passages |
| **Answer generation from retrieved context** | Users expect synthesized answers, not raw search results | High | Requires local LLM (LM Studio); must summarize/synthesize across multiple chunks |
| **Document metadata extraction** | 15-year archive requires filtering by date, author, document type, client | Medium | Parser metadata: doc title, creation date, format, length; manual tagging optional |
| **Query context window management** | LLM context is fixed; must fit retrieved chunks + query in token budget | Medium | Chunk selection, ranking, and truncation logic |
| **Incremental indexing** | Users will add new documents after initial load; re-indexing entire corpus is unacceptable | Medium | Delta processing: identify new docs, extract entities, add to graph |
| **Performance targets** | 32GB RAM + 4GB VRAM; < 1 min/doc indexing (per PROJECT.md) | High | Chunking strategy, embedding batch sizing, graph storage efficiency |
| **Local-only inference** | Air-gapped office laptop; no cloud/API calls allowed | High | All models (embedding + LLM) run on-device via LM Studio |

---

## Differentiators

Features that set this product apart. Not expected in basic RAG, but valuable for this consulting use case.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Knowledge graph visualization** | Consultants see entity relationships, communities, and cross-document themes visually | Medium-High | Shows connected entities, document bridges, relationship types (client→project→recommendation) |
| **Community/cluster detection** | Automatically find thematic groups in documents: "all supply-chain POVs," "all EV strategy work" | High | Graph-level clustering; requires community detection algorithm (Louvain, Leiden) |
| **Cross-document synthesis queries** | "What patterns emerge across all our EV proposals?" vs finding single documents | High | Multi-hop reasoning over graph; aggregate LLM synthesis across multiple entity paths |
| **Entity-scoped search** | Search by named entities (clients, technologies, concepts) rather than keywords | Medium | Extract + link entities; allow filtering: "show work with TESLA," "show BATTERY_PACK mentions" |
| **Document relationship mapping** | Auto-detect when documents reference or build on each other | Medium-High | Similarity clustering + temporal ordering; flag "this casetudy informed that proposal" |
| **Temporal analysis** | "What evolved in our approach to EV manufacturing from 2015 to 2024?" | Medium | Timeline view of themes, metadata date filtering, trend detection in entity mentions |
| **Manual verification workflow** | Flag tables/diagrams for human review; track which insights need validation | Low | UI checkbox: "needs manual review"; store verification status per chunk |
| **Query feedback loop** | Users rate answer quality; improve future queries without re-indexing | Low | Store user feedback (thumbs up/down); surface low-confidence answers for review |
| **Document similarity search** | "Find documents similar to this one" without writing a query | Low | Vector similarity to selected doc's embedding; useful for case study comparison |
| **Expert-in-the-room mode** | Ask follow-up questions within same conversation; build conversation context | Medium | Chat history management; context aggregation across multi-turn queries |
| **Structured export** | Export synthesis (e.g., "all supply chain findings") as markdown or formatted report | Low | Post-processing of chat outputs; useful for writing internal memos |

---

## Anti-Features

Explicitly DO NOT build these in v1. Reasons align with PROJECT.md constraints.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Visual/image embeddings** | v1 failure: colqwen2.5 took 5+ min/page; unusable on office hardware | Stick to text extraction; flag visuals for manual review; users can open PDFs separately |
| **OCR for scanned documents** | Adds latency; most consulting docs are born-digital PDFs; OCR errors reduce accuracy | Inform users: "document must be text-searchable PDF"; skip scans |
| **Multi-user authentication & auth controls** | Out of scope (PROJECT.md); adds complexity without immediate value | Single-user tool; trust users to self-police document access |
| **Real-time document streaming/sync** | No enterprise document management integration; batch indexing is sufficient | Manual "add folder of new docs" workflow; index runs in background |
| **Advanced NLP tasks (named entity normalization, relation extraction refinement)** | High complexity; marginal value for consultant use case; brittle across document types | Basic extraction; accept some noise; rely on graph to find correct nodes |
| **Structured data extraction from tables/charts** | "Too brittle" per PROJECT.md; parsing varies wildly by table format | Humans read tables; system flags them ("Table 3.1 in Supply_Chain_2022.pdf - manual review needed") |
| **LLM fine-tuning on your document corpus** | Adds latency to indexing; generic LLMs work well enough for synthesis; no retraining infrastructure | Use pre-trained quantized LLM (7-13B param); rely on RAG context, not tuning |
| **Conversational clarification loops** | "Did you mean X or Y?" chatbot politeness adds latency and complexity | Bare answers with citations; users refine if needed |
| **Full-text indexing with ranking/BM25 tuning** | Semantic search + chat should dominate; keyword tuning is low ROI | Basic keyword matching; prioritize vector similarity and LLM synthesis |

---

## Feature Dependencies

```
Document ingestion
  ├─ Text extraction (PDF + PPTX)
  └─ Metadata extraction (title, date, format)
      └─ Document filtering in UI

Entity/Relationship extraction
  ├─ Named entity recognition (NER)
  ├─ Relationship extraction (basic patterns)
  └─ Requires: Chunked text from ingestion

Graph construction
  ├─ Entity deduplication / linking
  ├─ Community detection
  └─ Requires: Entity/relationship extraction

Semantic search
  ├─ Chunk embeddings (via LM Studio)
  ├─ Vector similarity search
  └─ Requires: Document ingestion + chunking

Query answering
  ├─ Retrieved chunk ranking
  ├─ Context window management
  ├─ LLM synthesis (via LM Studio)
  └─ Requires: Semantic search + graph context

Chat UI
  ├─ Query input + formatting
  ├─ Answer generation display
  ├─ Source citation rendering
  ├─ Chat history
  └─ Requires: Query answering

Knowledge graph visualization (DIFFERENTIATOR)
  ├─ Entity node rendering
  ├─ Relationship edge drawing
  ├─ Community coloring
  └─ Requires: Graph construction + community detection

Cross-document synthesis (DIFFERENTIATOR)
  ├─ Multi-hop graph traversal
  ├─ LLM aggregation across paths
  └─ Requires: Query answering + graph traversal

Temporal analysis (DIFFERENTIATOR)
  ├─ Document date extraction
  ├─ Timeline UI
  ├─ Trend detection in entity mentions
  └─ Requires: Metadata extraction + entity indexing

Manual verification workflow
  └─ Requires: Chat UI (just add checkbox for flagging)

Query feedback loop
  └─ Requires: Chat UI (just add rating UI)
```

---

## MVP Recommendation

**Prioritize (Phase 1–2):**

1. **Document ingestion** (PDF + PPTX text extraction)
   - Critical blocker; nothing works without it
   - Complexity: Medium
   - Est. effort: 1–2 weeks

2. **Semantic search** (embeddings via LM Studio)
   - Core value: "find similar work"
   - Complexity: Medium
   - Est. effort: 1–2 weeks

3. **Query answering** (retrieve + synthesize via LLM)
   - Core value: "get cited answers"
   - Complexity: High (context management is tricky)
   - Est. effort: 2–3 weeks

4. **Chat UI** (query input, answer display, citations)
   - Required for consultant UX
   - Complexity: Low
   - Est. effort: 1 week

5. **Basic entity extraction + graph**
   - Enables graph-based retrieval in future phases
   - Complexity: Medium
   - Est. effort: 2 weeks

**Defer (Phase 3+):**

- **Knowledge graph visualization**: Nice-to-have; proof of concept via chat descriptions first
- **Community detection**: Valuable but can ship with simple clustering; advanced detection later
- **Cross-document synthesis queries**: Requires robust multi-hop reasoning; iterate after MVP validation
- **Temporal analysis**: Polish feature; add after core Q&A works
- **Manual verification workflow**: Simple flag feature; can add in Phase 2 with light effort
- **Query feedback loop**: Useful for iteration but not critical for v1 adoption

**Explicitly skip (v1):**

- Visual embeddings, OCR, multi-user auth, table parsing, LLM fine-tuning

---

## Feature Complexity Estimates

| Category | Feature | Estimated Effort | Blocking | Notes |
|----------|---------|------------------|----------|-------|
| **Ingestion** | PDF text extraction | 1–2 weeks | YES | Use pdfplumber or pypdf; straightforward |
| | PPTX text extraction | 1–2 weeks | YES | Use python-pptx; mostly boilerplate |
| | Metadata extraction | 3–5 days | Medium | Filename, file stats; optional custom fields |
| | Document deduplication | 1 week | Low | Hash-based or fuzzy matching; defer if time-constrained |
| **Embeddings** | LM Studio integration | 3–5 days | YES | OpenAI-compatible API; standard HTTP client |
| | Chunk embedding pipeline | 1 week | YES | Batch processing, error handling, progress tracking |
| | Vector storage (Qdrant/FAISS/similar) | 1 week | YES | Local vector DB; query interface |
| **Graph** | NER + relationship extraction | 2 weeks | Medium | Use spaCy or similar; noisy but acceptable |
| | Entity deduplication | 1 week | Medium | String matching + embedding similarity; iterative |
| | Graph storage (Neo4j/NetworkX) | 1 week | Medium | Local graph DB or in-memory for MVP |
| | Community detection | 2 weeks | Low | Nice-to-have; use networkx.algorithms.community |
| **Query/LLM** | Semantic search (vector DB query) | 3–5 days | YES | Vector similarity + re-ranking |
| | Context window management | 1 week | YES | Chunk selection, token counting, truncation |
| | LLM integration (LM Studio) | 3–5 days | YES | Prompt formatting, response parsing |
| | Answer generation + synthesis | 1 week | YES | Prompt engineering, dealing with hallucination |
| **UI** | Chat interface (web) | 1–2 weeks | YES | React or similar; query input, answer display |
| | Source citations rendering | 3–5 days | YES | Clickable document links, chunk highlighting |
| | Chat history management | 3–5 days | Medium | Save/load conversations; simple SQLite or JSON |
| | Document filtering UI | 1 week | Low | Filter by date, format, keyword; MVP can be basic |
| **Performance** | Chunking strategy optimization | 1 week | Medium | Semantic vs fixed-size; test on hardware |
| | Batch embedding efficiency | 1 week | Medium | GPU utilization, memory management |
| | Incremental indexing | 1 week | Medium | Delta processing for new docs |
| | Query response caching | 3–5 days | Low | Simple hash-based cache; low ROI early |

---

## Automotive Consulting Specifics

For this use case specifically, prioritize features that surface:

1. **Cross-proposal pattern matching**
   - "Show all supply chain analyses" → Requires entity tagging or community clustering
   - Complexity: Medium (keyword + graph clustering)

2. **Client/technology mention tracking**
   - "What work have we done with Tesla?" → Requires reliable entity extraction
   - Complexity: Medium (NER quality is variable)

3. **Temporal trends**
   - "How did our approach to batteries change 2019–2024?" → Requires date metadata + entity timeline
   - Complexity: Medium (filtering + aggregation)

4. **Case study / POV linking**
   - "Which case studies support this proposal?" → Requires document relationship detection
   - Complexity: High (similarity + temporal reasoning)

5. **Framework identification**
   - "What are our standard supply chain analysis frameworks?" → Requires pattern extraction
   - Complexity: High (synthesis requires good LLM + context)

**Recommendation:** Start MVP with features 1–2 (doable with basic NER + graph). Features 3–5 are differentiators; iterate after v1 validation.

---

## Sources & Confidence

| Area | Confidence | Source | Notes |
|------|-----------|--------|-------|
| **Graph construction fundamentals** | HIGH | Training knowledge (GraphRAG architecture, standard practices) | Core RAG patterns well-established |
| **Entity extraction + NER** | HIGH | spaCy, transformer-based NER patterns | Industry standard for document understanding |
| **Chunking strategies** | HIGH | LLM + RAG literature (semantic vs fixed-size) | Well-documented trade-offs |
| **LM Studio integration** | MEDIUM | Training knowledge (OpenAI-compatible API) | Assumed compatible; verify in implementation |
| **Community detection in knowledge graphs** | MEDIUM | Graph theory + networkx documentation | Algorithms proven; application to consulting docs is less tested |
| **GraphRAG specific feature set** | MEDIUM | Training knowledge through Feb 2025 | Rapid evolution; may have new features in recent releases (post Feb 2025) |
| **Automotive consulting workflow** | MEDIUM | Inferred from PROJECT.md context | Assumptions about consultant behavior; validate with users |
| **Performance targets (< 1 min/doc)** | MEDIUM | Hardware constraints + empirical v1 data | Achievable with text-only; actual performance TBD in implementation |

---

## Gaps to Address in Phase-Specific Research

1. **Graph technology choice** (Neo4j vs Qdrant + NetworkX vs in-memory): Defer to architecture phase
2. **NER model selection** (spaCy vs transformer-based): Defer to implementation; try both, pick based on speed
3. **Chunking strategy tuning** (semantic vs fixed vs recursive): Empirical testing required on actual docs
4. **LLM prompt engineering** for consulting context: Requires user feedback loops post-MVP
5. **Performance profiling** on office hardware: Build and measure; may need aggressive optimization
6. **User workflow validation** (how do consultants actually use the system?): Plan user testing in Phase 2

---

## Key Assumptions (for validation)

- **Assumption 1:** Consultants will use the system primarily for "find similar work" and "synthesize themes" queries (not general knowledge Q&A)
  - **Validation:** User interviews / prototype testing
  - **Risk:** If patterns are unexpected, feature prioritization changes

- **Assumption 2:** Text-only extraction is sufficient; consultants can manually review tables/diagrams
  - **Validation:** Analysis of actual document corpus (% tables vs text)
  - **Risk:** If critical insights are visual, need to revisit visual embedding approach

- **Assumption 3:** Generic entity extraction (NER) is good enough; no need for domain-specific relation extraction
  - **Validation:** Test NER accuracy on 50–100 documents
  - **Risk:** If entity quality is low, synthesis quality suffers; may need refinement

- **Assumption 4:** LM Studio can handle embedding + LLM on 4GB VRAM
  - **Validation:** Load-test with full corpus
  - **Risk:** May need smaller models or aggressive quantization

