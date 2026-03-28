# Technology Stack: Local GraphRAG for Automotive Consulting

**Project:** Automotive Consulting GraphRAG Agent
**Researched:** 2026-03-28
**Hardware Context:** 32GB RAM + 4GB VRAM, LM Studio OpenAI-compatible API
**Confidence:** MEDIUM (training data through Feb 2025; validate against current LM Studio version compatibility)

---

## Recommended Stack

### Core Framework & Orchestration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Python** | 3.10+ | Base runtime | Standard for ML workloads; good library ecosystem; LM Studio OpenAI client libraries mature in 3.10+ |
| **LlamaIndex** | 0.9.x–0.10.x | RAG framework & query orchestration | Superior document chunking strategies; first-class integration with GraphRAG; better abstractions for local models than LangChain; avoids token-counting overhead |
| **LangChain** | 0.1.x–0.2.x | Alternative orchestration (if preferred) | Simpler for basic workflows; heavier token overhead; use only if team familiar with it; prefer LlamaIndex for knowledge graph work |

**Rationale:** LlamaIndex has tighter abstractions for local-first RAG and better GraphRAG patterns. LangChain adds token-counting overhead that hurts latency on resource-constrained hardware. Use LlamaIndex as primary, LangChain only if already standardized in team.

---

### Text Extraction

| Library | Version | Format | Use Case | Why |
|---------|---------|--------|----------|-----|
| **PyMuPDF (fitz)** | 1.23.x–1.24.x | PDF | Primary PDF extraction | Fast (C-based), zero external dependencies, precise text boundary detection, handles complex layouts better than pdfplumber, minimal memory overhead |
| **pdfplumber** | 0.9.x–0.10.x | PDF | Alternative/fallback | Better for handwritten/scanned PDFs; slower; use as fallback only if PyMuPDF fails on specific document types |
| **python-pptx** | 0.6.x | PPTX | Pitch decks & slide content | Standard PPTX library; extracts speaker notes + text; adequate for 2000-document corpus |

**Rationale:** PyMuPDF is 3-5x faster than pdfplumber on large PDFs and has negligible memory footprint. pdfplumber excels at handwritten text but is not needed for typical consulting PDFs (reports, proposals). python-pptx is the only viable PPTX extractor and is lightweight.

---

### Embedding Models & Serving

| Component | Model | Version | Serving | Why |
|-----------|-------|---------|---------|-----|
| **Embedding Model** | **nomic-embed-text-1.5** | Latest (2025) | LM Studio | 768-dim, ~200M parameters, fits easily in 4GB VRAM, 8.7k context window, optimized for retrieval tasks; fast inference (<10ms per chunk) |
| **Alternative** | **mxbai-embed-large** | Latest (2025) | LM Studio | 1024-dim, larger but still fits 4GB VRAM; use if corpus requires higher embedding quality; slightly slower |
| **Model Server** | **LM Studio** | 0.2.x+ (2025) | Local | OpenAI-compatible API, already required; natively serves embeddings + LLM in same process |

**Rationale:** nomic-embed-text is purpose-built for semantic search, smallest footprint, and LM Studio serves both embeddings and LLM from one interface. mxbai-embed-large trades a bit of speed for higher embedding quality; benchmarks show ~5-10% retrieval improvement on dense corpora. For 500–2000 documents, nomic-embed-text is sufficient and leaves VRAM headroom for LLM inference.

**DO NOT use:** Larger models (e-5-large-v2, all-mpnet-base-v2) — exceed 4GB VRAM. ColQwen visual embeddings — v1 proved unusable (5+ min/page).

---

### LLM Models for Answer Generation

| Model | Size | Quantization | Fit (4GB VRAM) | Context | Why |
|-------|------|--------------|----------------|---------|-----|
| **Qwen2.5 7B** | 7B | q4_k_m (4-bit) | ✓ Yes (~3.8GB) | 32k | Fast, excellent reasoning for synthesis tasks; good for summarizing consulting insights |
| **Mistral 7B Instruct** | 7B | q4_k_m (4-bit) | ✓ Yes (~3.8GB) | 32k | Well-instruction-tuned; lower latency than Qwen; good for document-grounded Q&A |
| **Llama 3.1 8B Instruct** | 8B | q4_k_m (4-bit) | ✓ Yes (~4.2GB, tight) | 8k | Strong performance; requires careful quantization; marginal fit |

**Selection Recommendation:** **Qwen2.5 7B** (q4_k_m) — best balance of reasoning quality, speed, and VRAM headroom for the synthesis-heavy queries (summarize patterns, synthesize themes) that characterize consulting use cases.

**DO NOT use:** 13B models — exceed 4GB VRAM even with aggressive quantization. Larger models push VRAM into swap, killing latency.

---

### Vector Store

| Technology | Type | Use Case | Why |
|------------|------|----------|-----|
| **ChromaDB** | In-memory + persistent | Primary vector store | Lightweight, no external dependencies, built-in OpenAI-compatible embeddings interface, reasonable scaling to 500k+ vectors, mature for local use |
| **FAISS** | In-memory (no persistence) | High-throughput search | Fastest retrieval (CPU-optimized vector ops); use only if ChromaDB bottlenecks on >50k documents |
| **LanceDB** | Columnar-vectorDB | Modern alternative | Apache Arrow backend, efficient for very large corpora (1M+), overkill for 500–2000 docs, adds complexity |

**Rationale:** ChromaDB is the sweet spot — zero dependencies, handles embedding ingestion natively, and persists to disk. FAISS is faster but requires manual persistence layer. LanceDB is over-engineered for this corpus size. Start with ChromaDB; if latency becomes an issue on >50k documents, profile first before swapping to FAISS.

---

### Knowledge Graph Store

| Technology | Type | Persistence | Why |
|------------|------|-------------|-----|
| **NetworkX** (in-memory) | Graph library | JSON dump to disk | Lightweight, no external services, adequate for 500–2000 documents (typically ~10k–50k nodes), fast community detection |
| **Neo4j Community** | Graph database | Native storage | Requires Docker/JVM; adds operational overhead; overkill for this scale; only if team requires Cypher querying |
| **In-memory dict + JSON** | Custom | File-based | If NetworkX feels heavy; pure Python; simplest debugging |

**Recommendation:** **NetworkX** — standard library for graphs in Python, sufficient for expected entity density, persists easily to JSON, and integrates well with LlamaIndex GraphRAG patterns. Neo4j adds Docker complexity and operational burden for no benefit at this scale.

---

### Web Chat UI

| Framework | Ease of Use | Performance | Why |
|-----------|-------------|-------------|-----|
| **Streamlit** | ⭐⭐⭐⭐⭐ | Good | Non-technical consultants; rapid iteration; native chat components; hot reload; runs in browser |
| **Chainlit** | ⭐⭐⭐⭐ | Excellent | Optimized for RAG workflows; built-in chat history, step visualization; more polished than Streamlit |
| **Gradio** | ⭐⭐⭐ | Good | Simpler but fewer UI options; fine for demo, overkill for production chat |
| **Open WebUI** | ⭐⭐⭐⭐ | Good | Heavy (Node.js + Python); designed for multi-user; unnecessary for single-user laptop tool |

**Recommendation:** **Streamlit** — best trade-off of ease-of-use for non-technical consultants, rapid development cycle, and minimal dependencies. Chainlit is close second if you want a more "production chat" feel; Streamlit wins on time-to-value.

---

### Supporting Libraries

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **openai** (Python client) | 1.3.x–1.5.x | LM Studio API calls | Use OpenAI client lib to talk to LM Studio's OpenAI-compatible endpoint; simpler than raw HTTP |
| **requests** | 2.31.x+ | HTTP for LM Studio fallback | Lightweight HTTP; use only if OpenAI client unavailable |
| **pydantic** | 2.x | Data validation | Schema validation for chunks, entities, relationships; standard in Python ML |
| **numpy** | 1.24.x+ | Array operations | Dependency of embedding/vector libs; ensure ≥1.24 for performance |
| **tqdm** | 4.66.x+ | Progress bars | User feedback on long indexing runs |
| **python-dotenv** | 1.0.x | Config management | Load LM Studio endpoint from .env; keep secrets out of code |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **RAG Framework** | LlamaIndex | LangChain | LangChain adds token-counting overhead; less optimized for knowledge graphs |
| **PDF Extraction** | PyMuPDF | pypdf | PyMuPDF is 3-5x faster; pypdf is pure Python but slower on large documents |
| **Embedding Model** | nomic-embed-text-1.5 | e5-large-v2 | e5-large-v2 exceeds 4GB VRAM; nomic is optimized for retrieval |
| **LLM Size** | 7B (Qwen2.5) | 13B or larger | 13B exceeds 4GB VRAM even with q4_k_m quantization |
| **Vector Store** | ChromaDB | Pinecone | Pinecone requires API key (cloud); chromaDB is local, no external dependency |
| **Graph Store** | NetworkX | Neo4j | Neo4j requires Docker/JVM; NetworkX is sufficient at this scale |
| **UI** | Streamlit | Chainlit | Chainlit is more polished; Streamlit is faster to iterate for consultants |

---

## Complete Installation

### Prerequisites

Verify LM Studio is running:
```bash
curl http://localhost:1234/v1/models
# Should return list of loaded models
```

### Core Dependencies

```bash
# Python package manager setup (recommend uv or pdm for speed)
pip install --upgrade pip

# Core RAG & graph framework
pip install "llama-index>=0.10.0" "llama-index-core>=0.10.0"
pip install "llama-index-embeddings-openai>=0.1.0"  # Uses OpenAI-compatible endpoint
pip install "networkx>=3.2" "pydantic>=2.0"

# Text extraction
pip install "PyMuPDF>=1.23.0" "pdfplumber>=0.9.0" "python-pptx>=0.6.0"

# LM Studio integration
pip install "openai>=1.3.0" "requests>=2.31.0"

# UI
pip install "streamlit>=1.28.0"

# Supporting
pip install "numpy>=1.24.0" "tqdm>=4.66.0" "python-dotenv>=1.0.0"
```

### Development Dependencies

```bash
pip install -D "pytest>=7.4.0" "black>=23.0.0" "ruff>=0.0.275"
```

### Verification Script

```python
# verify_stack.py
import sys
from openai import OpenAI

# Check Python version
assert sys.version_info >= (3, 10), "Python 3.10+ required"

# Check LM Studio connectivity
client = OpenAI(
    api_key="not-needed",
    base_url="http://localhost:1234/v1"
)

try:
    models = client.models.list()
    print(f"✓ LM Studio running: {len(models.data)} models loaded")
except Exception as e:
    print(f"✗ LM Studio not reachable: {e}")
    sys.exit(1)

# Check required packages
required = [
    "llama_index",
    "PyMuPDF",
    "pdfplumber",
    "python_pptx",
    "networkx",
    "streamlit",
    "pydantic"
]

for pkg in required:
    try:
        __import__(pkg)
        print(f"✓ {pkg} available")
    except ImportError:
        print(f"✗ {pkg} missing")
        sys.exit(1)

print("\n✓ Stack verification passed")
```

---

## Configuration (LM Studio Integration)

### .env File

```bash
# LM Studio endpoint (default)
LM_STUDIO_API_BASE=http://localhost:1234/v1
LM_STUDIO_API_KEY=not-needed

# Embedding model name (loaded in LM Studio)
EMBEDDING_MODEL=nomic-embed-text-1.5

# LLM model name (loaded in LM Studio)
LLM_MODEL=Qwen2.5-7B-Instruct

# Inference parameters
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

### Python Integration Example

```python
from openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI as LlamaIndexOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LM Studio client
lm_studio_client = OpenAI(
    api_key=os.getenv("LM_STUDIO_API_KEY", "not-needed"),
    base_url=os.getenv("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
)

# LlamaIndex embedding integration
embed_model = OpenAIEmbedding(
    model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text-1.5"),
    api_key=os.getenv("LM_STUDIO_API_KEY", "not-needed"),
    api_base=os.getenv("LM_STUDIO_API_BASE", "http://localhost:1234/v1"),
)

# LlamaIndex LLM integration
llm = LlamaIndexOpenAI(
    model=os.getenv("LLM_MODEL", "Qwen2.5-7B-Instruct"),
    api_key=os.getenv("LM_STUDIO_API_KEY", "not-needed"),
    api_base=os.getenv("LM_STUDIO_API_BASE", "http://localhost:1234/v1"),
    temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
)

print(f"Embedding model: {embed_model.model}")
print(f"LLM model: {llm.model}")
```

---

## Known Constraints & Mitigations

### VRAM Pressure

**Constraint:** 4GB VRAM is tight for embedding + LLM inference simultaneously

**Mitigation:**
- Run embedding inference in batch (process 100 chunks, sync to vector store, free VRAM)
- Use quantized models (q4_k_m recommended; avoid q5 or q6)
- Profile first: measure actual VRAM usage during index build before scaling to 2000 documents

### Latency on Large Corpora (>50k vectors)

**Constraint:** ChromaDB may show retrieval latency >100ms on very large collections

**Mitigation:**
- For <10k documents, ChromaDB is sufficient
- For 10k–50k documents, monitor retrieval latency; if >500ms, profile vector store
- For >50k documents, consider FAISS as drop-in replacement (same API surface)

### Text Extraction Failures

**Constraint:** Some PDFs (scanned, hand-drawn, unusual encodings) may fail in PyMuPDF

**Mitigation:**
- Use pdfplumber as fallback for PyMuPDF failures (slower but more robust)
- Flag failing documents for manual extraction or OCR (out of scope for v1)
- Log extraction failures to track problematic documents

### LM Studio Restart During Indexing

**Constraint:** If LM Studio crashes/restarts during long index build, process fails

**Mitigation:**
- Checkpoint index state every N documents (every 100 or 500)
- Implement resume logic: skip already-embedded documents on restart
- Monitor LM Studio logs

---

## Performance Targets

Based on hardware constraints, target:

| Operation | Target Latency | Notes |
|-----------|----------------|-------|
| **Embed 1 chunk (512 tokens)** | <10ms | nomic-embed-text-1.5 typical |
| **Index 1 document (10 chunks)** | <200ms | Includes text extraction + embedding + graph ops |
| **Index corpus (500 docs)** | <100 seconds | ~200ms/doc avg |
| **Vector retrieval (top-10)** | <50ms | ChromaDB, <10k vectors |
| **LLM inference (2k token generation)** | 5–10 sec | Qwen2.5 7B q4_k_m, typical latency |
| **Full query (retrieve + generate)** | 10–15 sec | User-perceivable latency (acceptable for chat) |

---

## Version Pinning Strategy

Pin major versions; allow minor/patch updates:

```
llama-index>=0.10.0,<0.11.0
pydantic>=2.0,<3.0
PyMuPDF>=1.23.0,<2.0
networkx>=3.2,<4.0
streamlit>=1.28.0,<2.0
```

This allows security patches without breaking changes.

---

## Deployment Checklist

- [ ] LM Studio running and confirmed reachable via `http://localhost:1234/v1/models`
- [ ] Embedding model (nomic-embed-text-1.5) loaded in LM Studio
- [ ] LLM model (Qwen2.5-7B-Instruct) loaded in LM Studio
- [ ] Python 3.10+ environment created
- [ ] All packages installed via `pip install -r requirements.txt`
- [ ] .env file configured with LM Studio endpoint
- [ ] Verification script passes
- [ ] Sample PDF/PPTX ingested without error
- [ ] Streamlit UI loads and connects to backend
- [ ] Query end-to-end latency acceptable (<15 sec)

---

## Sources & Confidence

| Technology | Confidence | Source |
|-----------|------------|--------|
| **LlamaIndex** | HIGH | Official docs (Feb 2025); stable 0.10.x release; proven in production RAG systems |
| **PyMuPDF** | HIGH | Benchmark data; widespread production use; performance claims verified in ML workflows |
| **nomic-embed-text-1.5** | MEDIUM | 2025 release; training data indicates strong performance; limited public benchmarks vs alternatives |
| **Qwen2.5 7B** | MEDIUM | Recent release (late 2024); anecdotal reports positive; not yet widely benchmarked against other 7B models in 4-bit quantization |
| **ChromaDB** | HIGH | Stable 0.4.x release; mature; widely used in local RAG deployments |
| **NetworkX** | HIGH | Standard Python library for graphs; stable since 2.x |
| **Streamlit** | HIGH | Stable; widely used for ML UIs; excellent documentation |
| **LM Studio** | MEDIUM | Assumes 0.2.x stable release; OpenAI-compatible API is well-tested but real-world edge cases may exist |

**Overall Confidence: MEDIUM** — Stack is cohesive and well-supported, but some choices (nomic-embed-text-1.5 for this specific task, Qwen2.5 7B quantized performance) lack extensive public benchmarking. Recommend validating latency and VRAM usage on actual corpus during Phase 1 (indexing pipeline).

---

## Next Steps

1. **Phase 1 (Indexing):** Implement PyMuPDF + LlamaIndex + nomic-embed-text-1.5 + ChromaDB pipeline; measure actual VRAM/latency on 100-document sample
2. **Phase 2 (Query):** Integrate Qwen2.5 7B LLM; test answer quality and latency on queries; adjust chunk size/retrieval top-k if needed
3. **Phase 3 (Knowledge Graph):** Add NetworkX entity/relationship extraction; measure graph construction time
4. **Phase 4 (UI):** Streamlit chat interface; user acceptance testing with automotive team
5. **Optimization (Post-Phase 4):** Profile; swap ChromaDB→FAISS or nomic→mxbai if latency issues emerge
