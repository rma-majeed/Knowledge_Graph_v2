---
phase: 02-embedding-vector-search
plan: 02
type: execute
wave: 2
depends_on:
  - "02-01"
files_modified:
  - src/embed/embedder.py
autonomous: true
requirements:
  - EMBED-01

must_haves:
  truths:
    - "embed_chunks() calls client.embeddings.create() with batches of 8 texts and returns one vector per input chunk"
    - "embed_chunks() returns [] immediately for an empty input list without calling the API"
    - "embed_chunks() raises RuntimeError with message containing 'LM Studio' when the server is unreachable"
    - "embed_query() embeds a single string and returns a list[float] of length equal to model output dims"
  artifacts:
    - path: "src/embed/embedder.py"
      provides: "embed_chunks() and embed_query() implementations"
      exports:
        - "embed_chunks"
        - "embed_query"
  key_links:
    - from: "src/embed/embedder.py"
      to: "openai.OpenAI.embeddings.create"
      via: "client.embeddings.create(model=model, input=batch_texts)"
      pattern: "client\\.embeddings\\.create"
    - from: "src/embed/embedder.py"
      to: "httpx.ConnectError / openai.APIConnectionError"
      via: "except block raises RuntimeError"
      pattern: "RuntimeError.*LM Studio"
---

<objective>
Implement src/embed/embedder.py — the LM Studio embedding client.

Provides embed_chunks() for batch embedding during pipeline runs and embed_query()
for single-string embedding at query time (Phase 4). Uses the openai client against
LM Studio's OpenAI-compatible endpoint. Handles server-unavailable gracefully with
a clear RuntimeError rather than a raw connection error.

Purpose: EMBED-01 — chunks must be embedded via LM Studio API; this is the only
function that touches the network for Phase 2.

Output: src/embed/embedder.py (replaces NotImplementedError stub)
</objective>

<execution_context>
@/Users/2171176/.claude/get-shit-done/workflows/execute-plan.md
@/Users/2171176/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-embedding-vector-search/02-RESEARCH.md
@.planning/phases/02-embedding-vector-search/02-01-SUMMARY.md

@src/embed/embedder.py
</context>

<interfaces>
<!-- Phase 1 patterns for reference — embedder follows the same module conventions -->

From src/ingest/pipeline.py:
```python
# Pattern for batch processing with tqdm progress
from tqdm import tqdm
for item in tqdm(files, desc="Ingesting documents", unit="doc", disable=len(files) == 1):
    ...
```

From openai (1.93.0) — LM Studio compatible call:
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
response = client.embeddings.create(model="nomic-embed-text-v1.5", input=["text1", "text2"])
vectors = [item.embedding for item in response.data]  # list[list[float]]
```

LM Studio health check (httpx is installed as openai transitive dep):
```python
import httpx
def check_lm_studio(host: str = "localhost", port: int = 1234) -> bool:
    try:
        r = httpx.get(f"http://{host}:{port}/v1/models", timeout=2.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement embed_chunks() and embed_query() in src/embed/embedder.py</name>

  <read_first>
    - src/embed/embedder.py (current stub — read the function signatures to match exactly)
    - tests/test_embedding.py (read test_embed_chunks_calls_api, test_embed_chunks_server_unavailable, test_embed_chunks_empty_input, test_real_768_dim_vectors to understand what is expected)
    - .planning/phases/02-embedding-vector-search/02-RESEARCH.md (Pattern 1 and LM Studio API Reference — lines 91-145 and 312+)
  </read_first>

  <files>src/embed/embedder.py</files>

  <behavior>
    - test_embed_chunks_empty_input: embed_chunks([], client, model) returns [] and never calls client.embeddings.create
    - test_embed_chunks_calls_api: embed_chunks([{"chunk_text":"a"},{"chunk_text":"b"}], mock_client, model) calls mock_client.embeddings.create exactly once (both fit in one batch of 8); returns list of 2 vectors each len 768
    - test_embed_chunks_server_unavailable: when client.embeddings.create raises httpx.ConnectError, embed_chunks raises RuntimeError with "LM Studio" in the message
    - test_real_768_dim_vectors (integration): embed_chunks([{"chunk_text":"text"}], real_client, "nomic-embed-text-v1.5") returns list with one vector of length 768
  </behavior>

  <action>
Replace the NotImplementedError stub in src/embed/embedder.py with this implementation.

Key implementation rules:
1. Empty input guard: if not chunks, return [] immediately (no API call).
2. Batch loop: iterate chunks in slices of batch_size (default 8). For each batch:
   a. Extract texts: `[c["chunk_text"].strip() for c in batch]` — strip whitespace.
   b. Filter empty strings before embedding: if all texts in a batch are empty/whitespace,
      append `[[0.0] * 768 for _ in batch]` as placeholder vectors and continue.
   c. Call: `response = client.embeddings.create(model=model, input=texts)`
   d. Extract: `vectors = [item.embedding for item in response.data]`
   e. Accumulate into results list.
3. Error handling: wrap the embeddings.create call in try/except. Catch
   `(openai.APIConnectionError, httpx.ConnectError, httpx.TimeoutException)` and raise
   `RuntimeError(f"LM Studio server unavailable at localhost:1234 — {e!r}")`.
   Do NOT import openai at module level (lazy import inside function to keep tests fast).
4. embed_query(): calls embed_chunks with a single-item list wrapping the query text,
   returns the first element: `return embed_chunks([{"chunk_text": query_text}], client, model)[0]`

Final function signatures (must match stub exactly):
```python
def embed_chunks(
    chunks: list[dict],
    client: Any,
    model: str,
    batch_size: int = 8,
) -> list[list[float]]:

def embed_query(query_text: str, client: Any, model: str) -> list[float]:
```

Do NOT add tqdm progress bar to embed_chunks itself — the pipeline layer (Plan 04) owns
progress reporting. Keep this function pure: input chunks -> output vectors.

Do NOT call httpx for health check in this function — fail fast via the exception handler.
The pipeline layer pre-checks health before calling embed_chunks.
  </action>

  <verify>
    <automated>cd C:/Users/2171176/Documents/Python/Knowledge_Graph_v2 && python -m pytest tests/test_embedding.py::test_embed_chunks_calls_api tests/test_embedding.py::test_embed_chunks_server_unavailable tests/test_embedding.py::test_embed_chunks_empty_input -v 2>&1 | tail -10</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_embedding.py::test_embed_chunks_calls_api -v` exits 0 and shows PASSED (not xfailed)
    - `pytest tests/test_embedding.py::test_embed_chunks_server_unavailable -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_embed_chunks_empty_input -v` exits 0 and shows PASSED
    - `grep "raise NotImplementedError" src/embed/embedder.py` exits 1 (no longer a stub)
    - `grep "client.embeddings.create" src/embed/embedder.py` exits 0 (API call present)
    - `grep "RuntimeError" src/embed/embedder.py` exits 0 (error handling present)
    - `grep "batch_size" src/embed/embedder.py` exits 0 (batching implemented)
    - `python -m pytest tests/test_embedding.py -q -m "not integration" 2>&1 | grep -E "passed|xfailed"` — shows at least 3 passed, rest xfailed, exit 0
  </acceptance_criteria>

  <done>
embed_chunks() and embed_query() implemented. 3 unit tests pass (no longer xfail).
Full test suite still exits 0 (remaining stubs still xfail).
  </done>
</task>

</tasks>

<verification>
```
pytest tests/test_embedding.py -q -m "not integration"
```
Expected: 3 passed + 8 xfailed, exit code 0.

```
python -c "
from unittest.mock import MagicMock
from src.embed.embedder import embed_chunks
m = MagicMock()
m.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1]*768)])
result = embed_chunks([{'chunk_text': 'test'}], client=m, model='test-model')
assert len(result) == 1 and len(result[0]) == 768
print('embed_chunks OK')
"
```
</verification>

<success_criteria>
- embed_chunks([], client, model) returns []
- embed_chunks([chunk], mock_client, model) calls embeddings.create once and returns 1 vector
- embed_chunks raises RuntimeError containing "LM Studio" on connection failure
- 3 previously-xfail unit tests now PASSED
- No other tests regressed (full suite exits 0)
</success_criteria>

<output>
After completion, create `.planning/phases/02-embedding-vector-search/02-02-SUMMARY.md`
</output>
