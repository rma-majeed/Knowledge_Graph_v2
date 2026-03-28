# Domain Pitfalls: Local GraphRAG Document Intelligence

**Domain:** Local knowledge graph construction from document collections on constrained hardware (4GB VRAM, 32GB RAM)

**Researched:** 2026-03-28

**Overall Confidence:** MEDIUM
- High confidence on VRAM/hardware pitfalls (proven in v1 failure, well-documented in constrained inference)
- High confidence on graph explosion (known graph scaling problem, documented in entity extraction research)
- Medium confidence on chunking and entity deduplication (best practices vary by implementation; research limited by WebFetch access)
- Medium confidence on LM Studio API specifics (product-specific; requires ongoing testing during development)

---

## Critical Pitfalls

### Pitfall 1: Graph Explosion — Uncontrolled Entity/Relationship Growth

**What goes wrong:**
Graph becomes unusable: too many nodes/edges makes retrieval slow, memory bloated, and global queries meaningless ("community detection finds 200+ communities, each disconnected from the rest"). Naive entity extraction extracts *every* nominal phrase, creating tens of thousands of entities from 500–2000 documents. Graph operations (shortest path, community detection, dense ranking) time out or exhaust VRAM.

**Why it happens:**
- Entity extraction LLM too permissive ("extract all entities mentioned" → entity count grows O(n²) with document volume)
- No deduplication post-extraction → "Tesla Inc", "Tesla", "TSLA", "Tesla Motors" become separate nodes
- Relationship extraction too aggressive → creates edges for weak/implicit associations ("mentioned in same paragraph" ≠ semantic relationship)
- No graph pruning or filtering → keeps low-confidence or document-specific artifacts (e.g., "Q3 2024" as an entity node)

**Consequences:**
- Indexing phase balloons from minutes to hours (graph algorithms scale poorly)
- Query latency increases dramatically (1000+ entity nodes → retrieval traversal is expensive)
- VRAM OOM during community detection or global query aggregation
- Global answer synthesis fails because "community" becomes meaningless (all documents in one mega-community, or 200+ isolated micro-communities)
- User perceives system as broken ("why is my query taking 30 seconds?")

**Prevention:**
1. **Strict entity type filtering** — Extract only high-value entity types relevant to domain (for automotive consulting: OEMs, suppliers, technologies, financial metrics, regulatory frameworks). Reject generic/low-utility types (e.g., dates, quantities unless critical). Document whitelist in configuration.
2. **Relationship confidence thresholds** — Set minimum confidence score for extraction (recommend > 0.7). Discard low-confidence edges. Configuration: `relationship_confidence_threshold: 0.7`
3. **Entity extraction batch size limits** — Cap entities per document (e.g., max 50–100 entities per doc). If LLM extracts more, sample or rank by relevance score rather than keeping all.
4. **Relationship count limits** — Cap relationships per entity (e.g., max 20 outgoing edges per node). Prune lowest-confidence or most-redundant edges.
5. **Graph statistics monitoring** — Log entity/relationship growth during indexing. Alert if growth rate exceeds expected (e.g., > 200 entities per document suggests too-permissive extraction).
6. **Entity type cardinality check** — Some entity types should be small (e.g., "OEM" should be 5–20 nodes, not 500). Add post-extraction validation: if a type has >N nodes, flag for human review.

**Detection (warning signs):**
- Community detection produces >50 communities, or all documents merge into single community
- Entity count exceeds 10K for 500 docs (ratio > 20 entities/doc)
- Query latency > 5 seconds for global queries (community retrieval + synthesis)
- Community size is highly skewed (e.g., 1 huge community, 100+ singletons)
- VRAM usage spikes during graph operations (>2GB for 500 docs suggests bloat)

**Phase mapping:**
- **Phase 1 (Entity Extraction):** Define entity type whitelist and implement type filtering. Set relationship confidence thresholds in config. This prevents explosion at the source.
- **Phase 2 (Graph Construction):** Implement monitoring and pruning logic. Add entity/relationship caps and cardinality checks.
- **Phase 3 (Querying):** Monitor community detection performance. If slow, trace back to Phase 1 extraction settings.

---

### Pitfall 2: Chunking Strategy Mismatch — Wrong Chunk Size Kills Retrieval Quality

**What goes wrong:**
Chunks too large (e.g., 2000 tokens) → embedding represents multiple disconnected ideas, retrieval returns wrong documents or noisy context. Chunks too small (e.g., 100 tokens) → loses context, breaks semantic coherence, graph becomes too fragmented. RAG retrieval confidence drops because chunks don't align with actual content boundaries (paragraph/section breaks are ignored).

**Why it happens:**
- Default settings from reference implementations don't match document corpus (e.g., LLaMA2 configs assume arXiv papers, not business proposals)
- No domain analysis of what constitutes a "meaningful unit" (for automotive consulting: section > full proposal section, not arbitrary 512-token window)
- Chunk overlap ignored → documents can slip between chunks, creating gaps
- PPTX slides treated as full documents, not chunked appropriately (slide = coherent unit, should not be split)
- Token counting is approximate, actual token boundaries misaligned

**Consequences:**
- Graph built from chunks that don't represent semantic units → entities extracted from "boundary noise" (partial sentences, token fragments)
- Retrieval returns chunks that answer adjacent question, not the actual query
- Query quality degrades ("why does it keep returning Product X info when I ask about Supplier Y?")
- Embeddings less discriminative (large chunk = "about everything", small chunk = "too noisy")

**Prevention:**
1. **Domain-aware chunk sizing** — For business/consulting documents:
   - Analyze 20–30 sample documents → identify natural boundaries (sections, subsections, bullet lists)
   - Target: 300–600 tokens per chunk (automotive consulting sweet spot: full concept, fits in embedding context)
   - Configure: `chunk_size: 512`, `chunk_overlap: 100` (with actual token counting, not character estimation)
2. **Document type-specific chunking** — Different rules for PDF vs PPTX:
   - **PDF:** Chunk at section headers (h1/h2 boundaries), fall back to sentence/paragraph if > chunk_size
   - **PPTX:** One chunk per slide (slides are coherent units). If slide too long, chunk at bullet-point level
3. **Embedding quality validation** — Sample 50 random chunks, embed them, compute cosine similarity to adjacent chunks. If average similarity > 0.85, chunks too large (overlap). If < 0.3, chunks too small (disconnected).
4. **Entity extraction alignment** — Entities should be extracted per-chunk, not globally. Verify entities are grounded in the chunk they came from (prevent hallucination of entities not mentioned).
5. **Test chunking on retrieval quality** — After chunking, run test queries (20–30 of them). Track: (a) chunk retrieved, (b) is it relevant? (c) does it contain actual answer? Iterate chunk size until >80% retrieval precision.

**Detection (warning signs):**
- Entity extracted from a chunk, but entity name doesn't appear in the text
- Retrieval test shows chunks at boundaries (e.g., last sentence of chunk 1, first sentence of chunk 2, but query expects them together)
- Average chunk embedding similarity to adjacent chunks > 0.85 (too much overlap) or < 0.3 (too fragmented)
- Query returns correct document, wrong section (e.g., "EV supply chain" question returns "Company financials" chunk from same doc)
- Chunk size varies wildly (some 200 tokens, some 1200) — suggests inconsistent boundary detection

**Phase mapping:**
- **Phase 1 (Text Extraction & Chunking):** Define chunk_size, overlap, and domain rules. Validate on sample docs. This is *foundational* — wrong chunking cascades through entity extraction and retrieval.
- **Phase 2 (Entity Extraction):** Verify entities are chunk-grounded. Add quality check.
- **Phase 3 (Querying):** Monitor retrieval precision. If < 80%, revisit chunking strategy.

---

### Pitfall 3: Entity Deduplication Failure — Same Entity, Different Names → Fragmented Graph

**What goes wrong:**
"Tesla", "Tesla Inc", "Tesla Motors", "TSLA", "Tesla, Inc." are extracted as separate entities. Graph has four isolated nodes instead of one connected "Tesla" node. Queries about Tesla miss relationships/context that would have been found if entities were merged.

**Why it happens:**
- Named entity recognition (NER) doesn't normalize output (returns as-is from text)
- No coreference resolution (pronouns "it", "the company" not linked to named entity)
- No fuzzy matching for misspellings/variants (especially problematic in OCR'd PDFs)
- Entity linking not performed (no check: "does this entity already exist in graph?")
- Acronym expansion ignored (TSLA → Tesla)

**Consequences:**
- Graph fragmentation: 500 documents → 5000 entities become 8000+ after variants
- Relationship retrieval broken ("What does Tesla do?" returns different answers depending on which Tesla variant is queried)
- Community detection fails (entities should connect, but variants are isolated)
- Graph statistics misleading (appears 8K entities when really 5K unique)
- User frustration: query returns incomplete answer because deduplication missed connections

**Prevention:**
1. **Post-extraction entity normalization** — After LLM extracts entities, normalize:
   - Remove title case variations (Tesla → tesla, normalize to canonical form)
   - Expand acronyms using domain dictionary (TSLA → Tesla)
   - Remove legal suffixes (Inc, LLC, Ltd → base name only)
   - Handle common variants ("the Tesla company" → Tesla)
   - Configuration: Define normalization rules as regex + lookup table
2. **Fuzzy matching for deduplication** — Before adding entity to graph:
   - Check if similar entity already exists (Levenshtein distance < threshold, recommend 2)
   - If found, merge with existing node, log the merge decision
   - Keep track of entity aliases (Tesla→[Tesla, Tesla Inc, TSLA]) for query expansion
3. **Coreference resolution** — Link pronouns and coreferents to named entities:
   - "Tesla announced X. The company also said Y." → both sentences attributed to Tesla
   - Most challenging: requires NLP model or heuristics (full NLP model adds latency, not recommended on 4GB)
   - Fallback: Within-chunk coreference only (if pronoun + named entity in same chunk, link them)
4. **Entity canonical form storage** — Store both canonical form and aliases:
   ```json
   {
     "id": "entity_tesla_001",
     "canonical": "Tesla",
     "type": "OEM",
     "aliases": ["Tesla Inc", "Tesla Motors", "TSLA"],
     "confidence": 0.95
   }
   ```
5. **Domain-specific entity dictionary** — For automotive consulting, maintain curated list of known entities (OEMs, suppliers, regulatory bodies). During extraction, check if extracted entity matches dictionary, use canonical form from dictionary.

**Detection (warning signs):**
- Same entity appears with 3+ different names in graph (query entity endpoints, check for duplicates)
- Graph has >N% entity nodes that are fuzzy-duplicates of others (write query: find entities with Levenshtein distance < 3, compare counts)
- Relationship count is inconsistent (e.g., "Tesla" has 15 relationships, "TSLA" has 3, but query treats them separately)
- Entity aliases not tracked in output (can't tell user: "we call this Tesla (also: Tesla Inc, TSLA)")
- Community detection produces tiny clusters of 2-3 nodes that should be merged

**Phase mapping:**
- **Phase 1 (Entity Extraction):** Implement normalization + fuzzy deduplication immediately after LLM extraction. Core step, not deferrable.
- **Phase 2 (Graph Construction):** Add coreference linking (within-chunk minimum, more complex NLP optional for Phase 3+)
- **Phase 3 (Querying):** Implement query-time entity expansion (user queries "Tesla" → search also for aliases to improve recall)

---

### Pitfall 4: VRAM OOM — Model Doesn't Fit, System Crashes Mid-Indexing

**What goes wrong:**
System runs fine for first 100 documents, then crashes with CUDA OOM or out-of-memory error during indexing. Embedding model loads fine at start, but batch processing large chunks or graph operations exhaust 4GB. No recovery: restart required, progress lost.

**Why it happens:**
- Embedding model larger than assumed (e.g., intended 3B param model, actual 7B quantized)
- Batch size too large for inference (process 32 chunks at once instead of 4–8)
- Graph operations (community detection, dense ranking) load entire graph into memory at once
- No memory profiling during development (works on dev machine with 24GB VRAM, fails on production laptop with 4GB)
- LM Studio context window bloat (loading full conversation history, not trimmed prompts)
- Accumulation: embeddings + model + batch + graph operations all in memory simultaneously

**Consequences:**
- Indexing crashes after N documents, no restart-from-checkpoint capability
- Users lose trust ("tool crashes when I add documents")
- Cannot scale to 2000 documents without hardware upgrade (fundamental blocker)
- Development cycles slow (5-minute crash every iteration)

**Prevention:**
1. **Model size validation pre-deployment** — Before using any model:
   - Get exact quantized model size (HuggingFace, check .safetensors file)
   - Test on 4GB VRAM machine: load model, embed a document, check peak VRAM usage
   - Formula: Peak VRAM = Model size + Batch inference overhead. Recommend peak < 3.5GB (leave 500MB margin for OS/other processes)
   - If doesn't fit, downquantize (GGUF Q4_K_M instead of Q6_K) or switch model
2. **Batch size tuning** — Start conservative, scale up:
   - Test: embed 1 chunk, 2 chunks, 4 chunks, 8 chunks. Stop when VRAM usage > 3.5GB
   - Recommended starting batch: 4–8 chunks, adjust down if OOM
   - Configuration: `embedding_batch_size: 8` (not a global 32)
3. **Graph operation streaming** — Don't load entire graph into memory:
   - Community detection: process subgraphs, not monolithic graph
   - Dense ranking: compute per-community, aggregate results
   - Implement checkpointing: save progress after every 100 documents, allow resume
4. **Memory monitoring during indexing** — Log peak VRAM at each phase:
   ```
   [Indexing doc 500] Chunks processed: 234 | Peak VRAM: 3.2GB | Graph nodes: 2341
   [Indexing doc 501] Chunks processed: 235 | Peak VRAM: 3.8GB | Graph nodes: 2355 ← WARNING: near limit
   [Indexing doc 502] CUDA OOM at chunk 240
   ```
   Stop automatically if peak VRAM > 3.7GB, prompt user to lower batch size or skip documents
5. **Quantization standards** — Use consistent quantization:
   - Embedding model: GGUF Q4_K_M (good quality/size tradeoff for 1.5–3B models)
   - LLM model: GGUF Q4_K_M or Q5_K_M (LLM can be larger, 7–13B acceptable)
   - Test quantization: verify embedding quality doesn't degrade (sample test queries)
6. **LM Studio API tuning** — Configure conservatively:
   - Context window: don't use max (e.g., if 8K max, set to 4K to reduce memory)
   - Number of parallel requests: 1 (prevent concurrent inference spikes)
   - Temperature/sampling: keep simple (avoids extra computation)
   - Connection pooling: limit concurrent connections to avoid stacking

**Detection (warning signs):**
- VRAM usage creeps up over 3.5GB during normal indexing (should plateau or grow slowly)
- Graph operations slow down for corpus > 500 docs (O(n²) complexity not addressed)
- LM Studio response times spike when ingesting multiple documents (latency increases > 2x)
- Crash happens after N documents (N correlates with total graph size, suggests graph operation OOM)
- System becomes swappy (HDD thrashing, mouse lag) — indicates spilled-to-disk memory pressure

**Phase mapping:**
- **Phase 0 (Model Selection):** Validate model fit on 4GB machine before committing. Non-negotiable.
- **Phase 1 (Indexing Implementation):** Set batch sizes, add memory monitoring, implement checkpointing. This is infrastructure, not optional.
- **Phase 2 (Graph Construction):** Implement streaming for graph operations. Add indexing resume capability.
- **Phase 3 (Querying):** Monitor VRAM during query execution. Implement query result streaming if needed.

---

### Pitfall 5: LM Studio API Latency & Limits — Timeouts, Rate Limits, Context Windows

**What goes wrong:**
- Embedding request times out (LM Studio configured for single request at a time; batch of 100 chunks × 200ms each = 20 sec wait)
- LLM generation for answer synthesis hits context window limit mid-generation (loaded 50 chunks + prompt, exceeds model's 4K context, response truncated)
- Rate limiting not handled (client sends requests faster than LM Studio processes, some fail silently)
- Connection pooling exhausted (100 parallel embedding requests × concurrent ingestion, LM Studio can't handle, drops connections)
- Model crashes or hangs during inference (model enters bad state, client never receives response, timeout waits 30 sec, indexing stalls)

**Why it happens:**
- LM Studio is single-process, single-threaded for inference (not designed for high-concurrency)
- API doesn't expose actual context window (client assumes 8K, model trained on 4K)
- No explicit rate limiting in API (requests queued, timeouts assumed)
- Network latency ignored (LM Studio on same laptop, still 50–200ms per request)
- Prompt construction naïve (includes full retrieval results without truncation → exceeds context)

**Consequences:**
- Indexing hangs: waiting for embedding responses, client perceives system as frozen
- Answer synthesis fails silently: LLM response truncated, user sees incomplete answer
- Batch failures: 10% of requests timeout, indexing must retry, progress unclear
- Poor user experience: "Why does typing my question take 10 seconds to process?"

**Prevention:**
1. **Timeout & retry configuration** — Set explicit limits:
   - Embedding timeout: 10 seconds per request (LM Studio should respond in < 5s normally)
   - LLM timeout: 30 seconds per request (generation can take longer)
   - Retry strategy: 3 retries with exponential backoff (500ms, 1s, 2s) before failing
   - Configuration: `embedding_timeout_sec: 10, llm_timeout_sec: 30, max_retries: 3`
2. **Batch size limiting & queueing** — Don't blast LM Studio with parallel requests:
   - Max 1–2 concurrent embedding requests (LM Studio processes sequentially; excess requests queue on client side)
   - Queue with backpressure: if queue > 10, pause chunk processing, wait for model to catch up
   - Measure: log request queuing delay, if > 5 sec, log warning
3. **Context window validation** — Before querying LLM:
   - Test: send known prompt to model, count tokens in response, verify < context window
   - Set safe limit: if model claims 8K context, use 6K for synthesis (2K margin for safety)
   - Prompt construction: trim retrieval context if needed:
     ```
     System: You are a helpful assistant
     Context: [up to 6K tokens of top-K chunks, truncate if needed]
     Query: [user question]
     ```
   - Verify: count tokens before sending to LM Studio, reject if > safe limit
4. **Error handling & graceful degradation** — Handle partial failures:
   - If embedding fails for a chunk, log it, skip chunk, continue (don't crash)
   - If LLM synthesis times out, return best-effort answer from retrieval alone (with note: "synthesis incomplete")
   - Notify user of failures: "Could not process 3 chunks due to timeout" (transparency)
5. **Connection pooling & monitoring** — Reuse connections, monitor health:
   - Single persistent connection to LM Studio (avoid connection setup overhead)
   - Heartbeat check: every 30 seconds, send simple embedding to verify connection healthy
   - If heartbeat fails, log error, attempt reconnect (exponential backoff)
   - Monitor: log response latencies, alert if p95 latency > 500ms (indicates model overload)
6. **Model selection for concurrency** — Choose model suitable for inference load:
   - Smaller model (1.5–3B) → faster per-token generation, can handle more concurrent requests
   - Larger model (7B+) → slower, suitable only for single-user or batch processing
   - Recommendation for automotive consulting: 3B model for embeddings (e.g., all-MiniLM), 7–13B for LLM (e.g., Mistral or Llama-2)

**Detection (warning signs):**
- Embedding latency > 200ms per request (should be < 100ms on same laptop)
- LLM generation cuts off mid-sentence ("The company supplies to..." instead of full answer)
- Timeout errors during indexing (partial documents indexed before crash)
- Queue depth growing unbounded (100+ pending requests, indexing falling behind)
- LM Studio process high CPU but not responding to requests (model hung, needs restart)

**Phase mapping:**
- **Phase 1 (Integration with LM Studio):** Set timeout/retry config, implement request queuing, add logging. Critical for stability.
- **Phase 2 (Answer Synthesis):** Implement context window validation, prompt truncation. Prevent generation failures.
- **Phase 3 (Querying):** Add heartbeat monitoring, request latency tracking. Monitor real-world performance.

---

### Pitfall 6: PPTX Text Extraction Gaps — Bullet Points, Tables, Speaker Notes Missed

**What goes wrong:**
Text extraction from PPTX retrieves slide titles and some body text, but misses:
- Bullet points (especially nested bullets)
- Table content (especially headers, cell relationships)
- Speaker notes (often contain key synthesis/conclusions)
- Captions/labels in diagrams (text tied to shapes, extraction tools ignore)
- Slide numbers, footers (metadata treated as content)

Result: Important context from PPTX decks is lost, graph is incomplete, queries miss information that was literally in the deck.

**Why it happens:**
- PPTX is XML-based; text is scattered across multiple elements (`<a:t>` tags in slides.xml, each bullet in separate element)
- Standard text extraction tools (python-pptx, zipfile + regex) do sequential XML parsing, miss hierarchy
- Speaker notes are in separate XML file (notesSlide1.xml), require explicit parsing
- Tables represented as nested shapes + text, not as "table" element; extraction treats as free-form text
- Diagram labels tied to shape objects, not extracted unless explicitly looking for text properties on shapes

**Consequences:**
- Entity extraction misses business concepts encoded in bullets ("Key OEM challenges: supply chain, EV transition, cost reduction" → misses "OEM challenges" entity or loses context)
- Graph becomes incomplete (missing 20–40% of information from decks)
- Queries about deck content fail ("What challenges did we discuss?" returns no bullets)
- User trust erodes: "The answer is literally on slide 5, but the tool didn't find it"

**Prevention:**
1. **Robust PPTX parsing** — Use proper PPTX library with structural awareness:
   - Recommended: `python-pptx` with custom traversal for all text elements
   - Extract in order: slide title → body text → bullets → table cells → speaker notes → shape text
   - Maintain structure: preserve bullet hierarchy (level 1, level 2, etc.) as outline
   - Output format: structured text with explicit section markers:
     ```
     [Slide 1: Title]
     Investment Opportunities in EV Transition

     [Body]
     Market growth driven by regulatory mandates

     [Bullets]
     - OEM strategies shifting to electric
       - Tesla dominance in premium segment
       - Traditional OEMs catching up with 2025+ launches
     - Supply chain implications
       - Battery sourcing becoming critical
       - Legacy suppliers at risk

     [Speaker Notes]
     Emphasize Tesla's first-mover advantage.
     Suppliers should expect consolidation.
     ```
2. **Table extraction with semantics** — For tables, extract as structured data:
   - Extract table headers and map cells to columns
   - Output as CSV or structured JSON (not just flat text)
   - Entity extraction should recognize table structure ("Supplier X | Volume | Cost" → extract relationships, not just named entities)
3. **Speaker notes parsing** — Treat speaker notes as first-class content:
   - Extract from notesSlide XML explicitly
   - Associate with slide number/title for context
   - Chunk separately if large (speaker notes can be long, may need own chunks)
4. **Diagram/shape text extraction** — For diagrams:
   - Attempt to extract text from shape objects (not just main text boxes)
   - Keep context: "Label X appears in diagram on slide 5" (helps with grounding)
   - Flag diagrams as non-extractable if complex (defer to user for manual verification)
5. **Quality validation on PPTX corpus** — After implementing extraction:
   - Manually verify 10–20 PPTX decks: compare extracted text to actual content
   - Check: are all bullets present? Are tables readable? Are speaker notes included?
   - If > 10% content missing, revisit extraction logic
6. **Document metadata preservation** — Keep track of extraction completeness:
   ```json
   {
     "document": "proposal_ev_2024.pptx",
     "slides": [
       {
         "slide_num": 1,
         "title": "EV Transition Roadmap",
         "extraction_completeness": 1.0,
         "has_speaker_notes": true,
         "has_tables": false,
         "has_diagrams": true,
         "diagram_extraction_status": "partial"
       }
     ]
   }
   ```

**Detection (warning signs):**
- Queries about specific slides return no results (entity not found, but it's in the slide)
- Comparison of extracted text vs. original deck shows > 5% content missing
- Speaker notes never appear in retrieval (indicator: speaker notes parsing not implemented)
- Table data appears as unstructured free-form text ("SupplierA | 1000 units | $50M" instead of structured table)
- Bullets appear as run-on text ("Tesla dominance in premium segment Traditional OEMs...") instead of separated
- User reports: "I know this information is in the deck, but your tool can't find it"

**Phase mapping:**
- **Phase 1 (Text Extraction):** Implement comprehensive PPTX parsing (title, body, bullets, tables, speaker notes). This is foundational; skip it and 20% of content is lost.
- **Phase 2 (Entity Extraction):** Adjust entity extraction to handle structured content (tables, bullets) properly. Ensure entities extracted from all content types.
- **Phase 3 (Querying):** Monitor retrieval coverage. If PPTX queries underperform vs PDF, investigate extraction completeness.

---

### Pitfall 7: Incremental Indexing Not Implemented — Re-Index Entire Corpus Per New Document

**What goes wrong:**
User adds 1 new document. System re-indexes all 500 documents from scratch (5–10 hours). New document takes 30 seconds to index, but system wastes 9.5 hours re-processing old documents. Users can only batch-add documents every few days ("I'll add to the index tonight, check results tomorrow").

**Why it happens:**
- Graph construction assumes starting from empty state (no delta/diff mechanism)
- No checkpoint/persistence between indexing runs (graph not saved mid-way, rebuilt each time)
- Entity deduplication requires global view (is entity "Tesla" already in graph? Can't know without re-reading all docs)
- Community detection must re-run on full graph (changes to one document ripple through community assignments)

**Consequences:**
- Indexing cycle: days → unusable for active documents
- Users batch work ("I have 50 documents, wait until weekend to index them all")
- Feature feels broken: "Why can't I just add a new document and query it immediately?"
- Development slow: each test iteration re-indexes entire corpus (5–10 minutes per test)

**Prevention:**
1. **Graph persistence** — Save graph state after each document indexed:
   - Format: JSON or GraphML (serializable, inspectable)
   - Checkpoint every 50–100 documents (adjust based on graph size)
   - Load checkpoint on startup: "Found checkpoint at doc 243, resuming from doc 244"
   - Configuration: `checkpoint_interval_docs: 50`, `checkpoint_dir: ./data/checkpoints/`
2. **Incremental entity deduplication** — Instead of re-dedup all entities:
   - On new document: extract entities, compare *only* to existing entity names (not re-extract old docs)
   - Use fuzzy matching (Levenshtein) to check if "Tesla Inc" matches existing "Tesla" (O(n) where n = existing entities, not corpus size)
   - Add new entity if no match, merge if match found, update document->entity mapping
3. **Relationship incremental updates** — Don't rebuild relationships:
   - Extract relationships only from new document (O(new_doc_size), not O(corpus_size))
   - Add edges to graph (no re-computation of existing relationships)
   - Mark as "pending community re-detection" if graph topology changed significantly
4. **Deferred graph recomputation** — Community detection & dense ranking can be deferred:
   - Mark: "Graph has pending changes, community detection stale"
   - Recompute community detection when user next queries (happens once, results cached)
   - Acceptable latency: first query after indexing takes 30 seconds (recomputes), subsequent queries < 1 second
   - Tradeoff: slightly stale community structure for massive indexing speedup
5. **Batch indexing optimization** — If user adds multiple documents at once:
   - Index all new documents
   - Dedup entities across new docs (avoid creating duplicates within batch)
   - Merge with existing graph once (not N times)
   - Compute community detection once at the end
   - Result: 10 docs indexed in 5 minutes (vs 50 minutes if done sequentially)

**Detection (warning signs):**
- Indexing time increases linearly with corpus size (adding 1 doc to 1000-doc corpus takes 10+ minutes)
- No resuming from checkpoints (system must re-index if it crashes)
- Graph file on disk is same size after adding new document (suggests full re-serialization)
- User feedback: "Why can't I just add a new document?"

**Phase mapping:**
- **Phase 2 (Graph Construction):** Implement checkpointing and incremental entity deduplication. Deferred-recomputation strategy for community detection. This is not optional for usability.
- **Phase 3 (Querying):** Implement lazy community recomputation (triggers on first query if stale).

---

### Pitfall 8: Community Detection Misconfiguration — Too Many or Too Few Communities

**What goes wrong:**
- Too many communities: algorithm produces 200+ tiny clusters (10–50 node each). Global query runs, but each community answers independently, results are fragmented and contradictory.
- Too few communities: all documents merge into 2–3 huge communities (500 nodes each). Community structure meaningless, global query treats entire corpus as one entity.
- Hyperparameter mismatch: resolution parameter tuned for graphs with 10K nodes, but this graph has 2K nodes; results are off.

**Why it happens:**
- Default community detection algorithm (e.g., Louvain, Leiden) has tunable resolution parameter (regulates community size)
- No domain guidance on expected community count (automotive consulting should have 20–50 communities across 500 docs, not 200)
- Algorithm implementation varies (networkx Louvain vs igraph vs scipy — same parameter produces different results)
- Graph structure itself drives output (very dense graph → few large communities; sparse graph → many tiny communities)

**Consequences:**
- Global queries slow (200 communities × synthesis = 200 independent answers to aggregate)
- Global answer contradictory or redundant (same fact synthesized by multiple communities)
- User perceives system as broken ("why is the answer so long and repetitive?")
- Query latency unacceptable (synthesis bottleneck)

**Prevention:**
1. **Understand graph structure first** — Before tuning community detection:
   - Measure graph statistics:
     - Node count: should be 5–20 nodes per document (ratio: ~10K nodes for 500 docs)
     - Edge density: should be ~0.01–0.05 (sparse, not dense clique)
     - Degree distribution: average degree 5–10 (not all nodes highly connected)
   - These statistics inform community algorithm choice + hyperparameters
2. **Choose algorithm suited to corpus** — Recommend:
   - **Louvain** (fast, good for medium graphs): use for 1K–50K node graphs, well-behaved on document graphs
   - **Leiden** (more stable, slower): use if Louvain produces unstable results (varies between runs)
   - Avoid: Girvan-Newman (too slow for 10K+ nodes)
   - Test: run algorithm on sample 100-doc subgraph, measure stability (run 5 times, compare results)
3. **Tune resolution parameter** — Find sweet spot via iterative testing:
   - Start with resolution = 1.0 (Louvain default)
   - Test: resolution 0.5, 1.0, 1.5, 2.0
   - Measure: community count, average community size, modularity
   - Goal: 20–50 communities for 500 docs (adjust expectation based on actual entity count)
   - Configuration: `community_detection_resolution: 1.0` (domain-tuned)
4. **Validate community structure** — After detection, check:
   - Are communities semantically meaningful? (sample communities, inspect nodes)
   - Is modularity high (> 0.4)? (indicates good partitioning)
   - Are communities stable? (re-run detection 3 times, check if communities consistent)
5. **Sanity checks on community count** — Alert if outliers:
   ```
   Expected communities: 20–50 for 500-doc corpus
   Detected: 200 communities
   → WARNING: too many communities, consider lowering resolution

   Detected: 2 communities
   → WARNING: too few communities, consider raising resolution
   ```

**Detection (warning signs):**
- Community count > 3x expected (suggesting over-fragmentation)
- Largest community contains > 50% of nodes (suggesting over-concentration)
- Global query response > 5 seconds (indicates too many communities being synthesized)
- Communities are unstable (re-run detection, get different partitions)
- Modularity < 0.3 (indicates weak community structure)

**Phase mapping:**
- **Phase 2 (Graph Construction):** Implement community detection with tunable resolution. Validate structure on sample corpus.
- **Phase 3 (Querying):** Monitor global query latency. If > 5 sec, revisit community count and synthesis aggregation.

---

### Pitfall 9: LLM Hallucination in Graph Synthesis — LLM Invents Connections Not in Graph

**What goes wrong:**
User asks: "What do we recommend to EV-focused OEMs?" Graph contains relationships: OEM → EV transition, OEM → supply chain, but NOT OEM → "recommendation" relationship. LLM synthesizes answer: "We recommend rapid battery sourcing consolidation" — a fact not supported by any document/entity in the graph. User accepts answer, acts on it, later realizes it's unsupported.

**Why it happens:**
- LLM has pre-trained knowledge (trained on automotive industry data, can generate plausible-sounding recommendations)
- Prompt doesn't enforce grounding ("answer based on the knowledge graph")
- Retrieval yields context, but LLM still has freedom to extrapolate ("based on A and B, I infer C")
- User doesn't know which facts come from documents vs LLM inference

**Consequences:**
- False answers propagate ("I read on this tool that...")
- User distrust ("why should I trust answers I can't verify?")
- Liability risk (consulting recommendations based on hallucinations)
- Tool becomes dangerous rather than helpful

**Prevention:**
1. **Strict grounding in prompts** — LLM instructions must enforce graph-based answers:
   ```
   System: You are a helpful assistant answering questions about automotive consulting insights.
   You MUST base your answers only on the provided knowledge graph.
   Do not infer, extrapolate, or use outside knowledge.
   If the answer is not in the graph, say "This information is not available in our documents."

   Knowledge Graph:
   [Entities and relationships from retrieval]

   Question: [User question]

   Answer: [Must cite entities/relationships from graph above]
   ```
2. **Retrieval-augmented strict grounding** — Don't just provide graph, also provide source text:
   ```
   Knowledge Graph Entities:
   - Tesla (OEM)
   - Supply chain (concern)
   - Battery sourcing (topic)

   Relationships:
   - Tesla → addresses supply chain challenges
   - Supply chain → impacts battery sourcing

   Source Evidence:
   - Document 1, page 3: "Tesla's battery sourcing strategy relies on..."
   - Document 5, page 12: "Supply chain constraints limit EV transition pace"

   Now answer, citing evidence above: [User question]
   ```
3. **Answer verification checklist** — After LLM generates answer, verify:
   - Does answer reference entities from graph? (should cite at least 3 entities)
   - Does answer cite source documents? (should reference specific pages/chunks)
   - Is answer verifiable by reading cited documents? (manual spot check: does the answer match what the document says?)
   - Are there unsupported claims? (flag for user review)
4. **Confidence scoring** — Tell user when answer is low-confidence:
   ```
   Answer: [LLM synthesis]

   Confidence: HIGH
   - Based on 12 documents
   - Multiple independent sources confirm
   - Direct quotes from source material

   OR

   Confidence: LOW
   - Based on limited sources (2 documents)
   - Inference required (not directly stated)
   - Recommend manual verification
   ```
5. **Chain-of-thought verification** — Force LLM to show its reasoning:
   ```
   Question: What supply chain strategies do OEMs use?

   Thinking:
   1. I found 8 entities of type "OEM" in the graph
   2. These entities have 23 relationships to "supply chain" topics
   3. Documents mention strategies: vertical integration, supplier consolidation, battery sourcing
   4. I'm now synthesizing based on these facts

   Answer: [synthesis with citations]
   ```
6. **Citation enforcement** — Every factual claim must cite source:
   - Claim: "Tesla focuses on battery sourcing" → [cite: Document X, page Y]
   - Claim: "Supply chain consolidation is likely" → [cite: Documents A, B, C or FLAG: inference not directly supported]
   - Tool should reject LLM output if claims uncited

**Detection (warning signs):**
- User fact-checks answer, can't find support in original documents ("I don't see that in the proposal")
- LLM answer introduces entities not in graph (mentions "Supplier X" but "Supplier X" not in graph)
- Confidence level mismatch (LLM answers with certainty despite weak evidence)
- Answer differs across similar queries (suggests LLM is generating vs. retrieving)
- User feedback: "The tool said X, but when I read the original documents, they say Y"

**Phase mapping:**
- **Phase 2 (Answer Synthesis):** Implement strict grounding prompts, source citation, confidence scoring. Not optional.
- **Phase 3 (Querying):** Add chain-of-thought verification, citation enforcement. Monitor hallucinations in user feedback.

---

## Moderate Pitfalls

### Pitfall 10: Query Latency Expectations — Global Queries Slow Due to Graph Traversal

**What goes wrong:**
User types a global query ("What are the top themes across our proposals?"). System must traverse graph, find communities, synthesize across all of them. Response takes 30–60 seconds. User perceives system as broken ("why is a simple question taking so long?").

**Why it happens:**
- Community detection and global aggregation are computationally expensive (must visit many nodes)
- LLM synthesis is sequential (generate answer for community 1, then 2, then 3...)
- No caching (if user asks same question twice, re-compute from scratch)

**Prevention:**
1. Set user expectations (document in UI: "Global queries may take 30–60 seconds")
2. Implement query result caching (same question asked again returns instantly)
3. Parallelize community synthesis (generate answers for 5 communities in parallel, not sequentially)
4. Implement query-time timeouts (if query > 45 sec, return partial results from first 10 communities)

**Detection:** Global query latency > 60 seconds

**Phase mapping:** Phase 3 (Querying) — optimization, not blocking

---

### Pitfall 11: PDF Text Corruption — OCR Artifacts, Encoding Errors, Scrambled Text

**What goes wrong:**
PDF extracted text has garbage: "Supply ÐœÐ°Ð¹ chain" instead of "Supply chain", "suppl ychain" (space in middle), CJK characters in English documents. Entity extraction fails (entity is gibberish), retrieval returns corrupted results.

**Why it happens:**
- PDF may be scanned (image), not text-based (requires OCR, not in scope)
- PDF encoding mismatches (document uses Windows-1252, tool assumes UTF-8)
- PDF extraction tool mishandles special characters or multi-line text

**Prevention:**
1. Text validation: after extraction, check for encoding errors (> 5% non-UTF8 bytes → skip document)
2. Corruption detection: if extracted text has > 10% garbage characters, flag document for OCR
3. Character normalization: fix common corruption patterns

**Detection:** Extracted text has > 5% non-UTF8 or unprintable characters

**Phase mapping:** Phase 1 (Text Extraction) — validation step

---

## Minor Pitfalls

### Pitfall 12: No Document Metadata Tracking — Can't Trace Answer Back to Source

**What goes wrong:**
User gets answer. Asks "Where did you find this?" Tool can't say (no source tracking). User distrust increases.

**Prevention:**
1. Track document metadata (filename, date, author, page number) with each chunk
2. Return source in query results: [Answer] sourced from [Document X, pages 3-5]

**Phase mapping:** Phase 1 (Ingestion) — include metadata extraction

---

### Pitfall 13: Graph Visualization Absent — Developers Can't Debug Graph Structure

**What goes wrong:**
Graph seems wrong (too many entities, bad community structure), but without visualization, hard to diagnose.

**Prevention:**
1. Implement graph visualization (export to Cytoscape JSON or similar)
2. Use for debugging during development, not user-facing

**Phase mapping:** Phase 2 (Graph Construction) — debugging tool

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|----------------|-----------|
| **Phase 1: Text Extraction** | PDF/PPTX parsing | Missing tables, bullets, speaker notes (Pitfall 6) | Implement comprehensive extraction with validation |
| **Phase 1: Chunking** | Chunk size selection | Chunks too large/small breaks retrieval (Pitfall 2) | Domain-specific sizing with test validation |
| **Phase 1: Embedding Model** | Model selection | Model too large for 4GB VRAM (Pitfall 4) | Validate fit on target hardware before commit |
| **Phase 2: Entity Extraction** | Entity filtering | Graph explosion from over-permissive extraction (Pitfall 1) | Strict entity type whitelist + confidence thresholds |
| **Phase 2: Entity Deduplication** | Normalization | Same entity as 4+ variants → fragmented graph (Pitfall 3) | Implement fuzzy matching + canonical forms immediately |
| **Phase 2: Graph Construction** | Community detection | Too many or too few communities (Pitfall 8) | Validate graph stats, tune resolution parameter |
| **Phase 2: Indexing** | Incremental updates | Re-indexing entire corpus per new document (Pitfall 7) | Implement checkpointing and delta indexing |
| **Phase 2: VRAM** | Memory management | OOM during graph operations (Pitfall 4) | Memory monitoring, batch size tuning, streaming |
| **Phase 3: LM Studio Integration** | API reliability | Timeouts, context window limits, rate limiting (Pitfall 5) | Timeout config, request queueing, window validation |
| **Phase 3: Answer Synthesis** | LLM grounding | LLM hallucination — answers not in graph (Pitfall 9) | Strict prompts, source citation, confidence scoring |
| **Phase 3: Query Latency** | Performance | Global queries slow due to graph traversal (Pitfall 10) | Caching, parallelization, early cutoffs |

---

## Summary for Roadmap

**Most Critical Pitfalls (address in early phases):**
1. **Graph Explosion (Pitfall 1)** — Wrong entity filtering creates unusable graph
2. **Chunking Strategy (Pitfall 2)** — Wrong chunk size breaks retrieval
3. **Entity Deduplication (Pitfall 3)** — Fragmentary graph from variant names
4. **VRAM OOM (Pitfall 4)** — System crashes on constrained hardware
5. **PPTX Extraction (Pitfall 6)** — Missing 20% of deck content

**Phase Sequencing Impact:**
- Phase 1 foundations (extraction, chunking) determine Phase 2 feasibility (graph construction). Get these wrong → Phase 2 is uphill.
- Phase 2 graph construction (entity deduplication, community detection) determines Phase 3 query quality. Sloppy dedup → queries fail.
- Phase 3 LLM integration (grounding, citation) determines user trust. Hallucinations → tool unusable.

**Validation Gates:**
- Phase 1 complete: chunk size validated on retrieval tests (>80% precision)
- Phase 2 complete: graph stats within expected bounds (entity count, community count, VRAM usage)
- Phase 3 complete: answer grounding verified (>90% of claims cited, <5% hallucinations in user testing)

---

## Sources

This PITFALLS.md synthesizes knowledge from:
- Local GraphRAG implementation research (constrained hardware patterns, common failures)
- Document intelligence best practices (chunking, entity extraction, deduplication)
- Graph construction scaling literature (community detection, graph explosion, entity matching)
- LLM grounding research (hallucination mitigation, citation enforcement)
- LM Studio operational experience (latency, context window, concurrency limits)

Confidence levels:
- **HIGH** on VRAM/hardware pitfalls (proven in v1, well-documented)
- **MEDIUM** on graph construction pitfalls (best practices exist, specific implementation varies)
- **MEDIUM** on LM Studio specifics (requires ongoing validation during development)
- **LOW** on PPTX-specific extraction issues (insufficient direct research, inferred from general document processing)
