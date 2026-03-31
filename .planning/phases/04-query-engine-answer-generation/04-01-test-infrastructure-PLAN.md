---
phase: 04-query-engine-answer-generation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/query/__init__.py
  - src/query/retriever.py
  - src/query/assembler.py
  - src/query/pipeline.py
  - tests/test_query_retriever.py
  - tests/test_query_assembler.py
  - tests/test_query_pipeline.py
  - conftest.py
autonomous: true
requirements:
  - QUERY-01
  - QUERY-02
  - QUERY-03
  - QUERY-04
  - QUERY-05

must_haves:
  truths:
    - "pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q collects all stubs and reports xfail (not errors or import failures)"
    - "All src/query/*.py files exist and raise NotImplementedError when called"
    - "conftest.py registers the lm_studio pytest marker so -k 'not lm_studio' works without warnings"
  artifacts:
    - path: "src/query/__init__.py"
      provides: "Package marker for src.query module"
    - path: "src/query/retriever.py"
      provides: "NotImplementedError stubs for vector_search, graph_expand, deduplicate_chunks, hybrid_retrieve"
    - path: "src/query/assembler.py"
      provides: "NotImplementedError stubs for truncate_to_budget, build_citations, format_answer, build_prompt"
    - path: "src/query/pipeline.py"
      provides: "NotImplementedError stub for answer_question"
    - path: "tests/test_query_retriever.py"
      provides: "xfail stubs covering QUERY-02 and QUERY-03"
    - path: "tests/test_query_assembler.py"
      provides: "xfail stubs covering QUERY-04"
    - path: "tests/test_query_pipeline.py"
      provides: "xfail stubs covering QUERY-01 and QUERY-05 (lm_studio-marked integration test)"
  key_links:
    - from: "tests/test_query_retriever.py"
      to: "src/query/retriever.py"
      via: "from src.query.retriever import ..."
      pattern: "from src.query.retriever import"
    - from: "tests/test_query_assembler.py"
      to: "src/query/assembler.py"
      via: "from src.query.assembler import ..."
      pattern: "from src.query.assembler import"
    - from: "tests/test_query_pipeline.py"
      to: "src/query/pipeline.py"
      via: "from src.query.pipeline import answer_question"
      pattern: "from src.query.pipeline import"
---

<objective>
Create the Wave 1 test scaffold and src/query package stubs for Phase 4 Query Engine & Answer Generation.

Purpose: Establish xfail test stubs and NotImplementedError source stubs before implementation begins. This mirrors the Wave 1 pattern used in Phases 2 and 3 exactly. All stubs become passing once plans 04-02, 04-03, and 04-04 implement the real code.

Output: 3 test files with xfail stubs (11 stubs total), 4 src/query module stubs, conftest.py updated with lm_studio marker registration.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/04-query-engine-answer-generation/04-RESEARCH.md
@.planning/phases/04-query-engine-answer-generation/04-VALIDATION.md

<interfaces>
<!-- Established xfail stub pattern from Phase 3 Wave 1 (03-01-test-infrastructure-PLAN.md) -->
```python
@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_example() -> None:
    """Docstring describing what will be tested."""
    raise NotImplementedError
```

<!-- NotImplementedError stub pattern for source modules -->
```python
"""Stub — Phase 4 plan 0N implements this."""
def function_name(*args, **kwargs):
    raise NotImplementedError
```

<!-- lm_studio marker: must be registered in conftest.py -->
# conftest.py already has "integration" marker — add lm_studio alongside it
```python
def pytest_configure(config):
    config.addinivalue_line("markers", "lm_studio: requires LM Studio running at localhost:1234")
```

<!-- ChromaDB ephemeral client for tests (never PersistentClient in tests) -->
import chromadb
client = chromadb.EphemeralClient()

<!-- KuzuDB temp dir for tests -->
import tempfile, kuzu
tmp = tempfile.mkdtemp()
db = kuzu.Database(tmp)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/query package stubs and register lm_studio marker</name>
  <files>src/query/__init__.py, src/query/retriever.py, src/query/assembler.py, src/query/pipeline.py, conftest.py</files>

  <read_first>
    - conftest.py (entire file — find pytest_configure to add lm_studio marker without breaking existing markers)
    - src/graph/__init__.py (replicate the empty package marker pattern)
  </read_first>

  <action>
1. Create `src/query/__init__.py` as an empty package marker:
```python
"""Query engine package — Phase 4."""
```

2. Create `src/query/retriever.py` with NotImplementedError stubs for all public functions:
```python
"""Hybrid retriever stub — implemented in plan 04-02.

Public API (all raise NotImplementedError until plan 04-02):
    vector_search(query_text, openai_client, chroma_path, embed_model, n_results) -> list[dict]
    graph_expand(vector_chunks, sqlite_conn, kuzu_db, n_per_entity) -> list[dict]
    deduplicate_chunks(chunks) -> list[dict]
    hybrid_retrieve(query_text, openai_client, sqlite_conn, kuzu_db, chroma_path, embed_model, n_results) -> list[dict]
"""
from __future__ import annotations


def vector_search(query_text, openai_client, chroma_path="data/chroma_db",
                  embed_model="nomic-embed-text-v1.5", n_results=10):
    """Embed query_text and retrieve top-N chunks from ChromaDB."""
    raise NotImplementedError


def graph_expand(vector_chunks, sqlite_conn, kuzu_db, n_per_entity=5):
    """Expand retrieval via 1-hop KuzuDB graph traversal seeded from vector_chunks."""
    raise NotImplementedError


def deduplicate_chunks(chunks):
    """Deduplicate chunk list by chunk_id, preserving order."""
    raise NotImplementedError


def hybrid_retrieve(query_text, openai_client, sqlite_conn, kuzu_db,
                    chroma_path="data/chroma_db", embed_model="nomic-embed-text-v1.5",
                    n_results=10):
    """Run vector_search + graph_expand + deduplicate_chunks in sequence."""
    raise NotImplementedError
```

3. Create `src/query/assembler.py` with NotImplementedError stubs:
```python
"""Context assembler and citation builder stub — implemented in plan 04-03.

Public API (all raise NotImplementedError until plan 04-03):
    truncate_to_budget(chunks, token_budget) -> tuple[str, list[dict]]
    build_citations(included_chunks) -> list[dict]
    format_answer(llm_response, citations) -> str
    build_prompt(query, context_str) -> list[dict]

Constants (available now for tests):
    CONTEXT_TOKEN_BUDGET = 3000
    CITATION_HIGH_CONFIDENCE_THRESHOLD = 3
"""
from __future__ import annotations

CONTEXT_TOKEN_BUDGET = 3000
CITATION_HIGH_CONFIDENCE_THRESHOLD = 3


def truncate_to_budget(chunks, token_budget=CONTEXT_TOKEN_BUDGET):
    """Sort chunks by relevance, truncate to token_budget, return (context_str, included)."""
    raise NotImplementedError


def build_citations(included_chunks):
    """Build citation list with HIGH/LOW confidence from included_chunks."""
    raise NotImplementedError


def format_answer(llm_response, citations):
    """Format LLM answer string with appended citation table."""
    raise NotImplementedError


def build_prompt(query, context_str):
    """Build messages list [system, user] for LM Studio chat API."""
    raise NotImplementedError
```

4. Create `src/query/pipeline.py` with NotImplementedError stub:
```python
"""Query pipeline stub — implemented in plan 04-04.

Public API (raises NotImplementedError until plan 04-04):
    answer_question(question, conn, kuzu_db, chroma_path, embed_model, llm_model, n_results) -> dict

Returns dict with keys: answer (str), citations (list[dict]), elapsed_s (float).
"""
from __future__ import annotations

DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"


def answer_question(question, conn, kuzu_db, chroma_path="data/chroma_db",
                    embed_model=DEFAULT_EMBED_MODEL, llm_model=DEFAULT_LLM_MODEL,
                    n_results=10):
    """Run hybrid retrieval + context assembly + LLM generation for question.

    Returns:
        dict with keys: answer (str), citations (list[dict]), elapsed_s (float)
    """
    raise NotImplementedError
```

5. Edit `conftest.py` to register the `lm_studio` marker. Read the file first, then add:
```python
    config.addinivalue_line(
        "markers", "lm_studio: requires LM Studio running at localhost:1234 with correct model loaded"
    )
```
inside the existing `pytest_configure` function (add after the existing `addinivalue_line` calls).
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -c "from src.query.retriever import hybrid_retrieve; from src.query.assembler import truncate_to_budget, CONTEXT_TOKEN_BUDGET; from src.query.pipeline import answer_question; print('stubs OK')"</automated>
  </verify>

  <done>All 4 src/query/*.py stubs created and importable; lm_studio marker registered in conftest.py; python -c import exits 0</done>
</task>

<task type="auto">
  <name>Task 2: Create xfail test stubs for retriever, assembler, and pipeline</name>
  <files>tests/test_query_retriever.py, tests/test_query_assembler.py, tests/test_query_pipeline.py</files>

  <read_first>
    - tests/test_citations.py (Phase 3 xfail pattern with real imports — replicate structure)
    - conftest.py (confirm lm_studio marker is registered before writing @pytest.mark.lm_studio)
  </read_first>

  <action>
Create three test files following the established xfail pattern. All tests use `@pytest.mark.xfail(strict=False, reason="not implemented yet")` and raise NotImplementedError. Tests will auto-pass once plans 04-02, 04-03, 04-04 implement the real code.

**tests/test_query_retriever.py** (covers QUERY-02 and QUERY-03):
```python
"""Tests for src/query/retriever.py — hybrid retrieval (QUERY-02, QUERY-03).

All tests are xfail stubs. They become passing once plan 04-02 implements
vector_search(), graph_expand(), deduplicate_chunks(), and hybrid_retrieve().

Test isolation:
  - ChromaDB: chromadb.EphemeralClient() — never PersistentClient
  - KuzuDB: tempfile.mkdtemp() for each test that needs a graph database
  - LM Studio: unittest.mock.MagicMock for openai.OpenAI client
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_search_returns_chunks() -> None:
    """vector_search() embeds query and returns list of chunk dicts from ChromaDB.

    Expected: returns list of dicts with keys chunk_id, text, metadata, distance.
    Uses chromadb.EphemeralClient() with a pre-populated collection.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_graph_expansion_finds_neighbors() -> None:
    """graph_expand() finds 1-hop neighbors in KuzuDB and fetches their chunks.

    Expected: given vector_chunks citing a known entity, graph_expand() returns
    additional chunk dicts from neighbor entities. Uses tempfile.mkdtemp() KuzuDB.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_dedup_merged_chunks() -> None:
    """deduplicate_chunks() removes duplicates by chunk_id, preserving order.

    Expected: a list with one duplicate chunk_id returns a list with that chunk_id
    appearing only once; total length is reduced by the duplicate count.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_hybrid_retrieve_combines_sources() -> None:
    """hybrid_retrieve() returns union of vector and graph chunks, deduped.

    Expected: result includes chunks with source='vector' and source='graph';
    no chunk_id appears more than once; result is a non-empty list.
    """
    raise NotImplementedError
```

**tests/test_query_assembler.py** (covers QUERY-04):
```python
"""Tests for src/query/assembler.py — context assembly and citation scoring (QUERY-04).

All tests are xfail stubs. They become passing once plan 04-03 implements
truncate_to_budget(), build_citations(), format_answer(), and build_prompt().
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_assemble_context_respects_token_budget() -> None:
    """truncate_to_budget() stops adding chunks when token budget is exhausted.

    Expected: given chunks whose total token count exceeds CONTEXT_TOKEN_BUDGET,
    truncate_to_budget() returns only the highest-relevance subset that fits.
    Vector chunks (source='vector') are prioritised over graph chunks (source='graph').
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_citation_confidence_high() -> None:
    """build_citations() assigns HIGH confidence when source doc+page appears >= 3 times.

    Expected: a chunk list where the same (filename, page_num) pair appears in
    3 or more included chunks produces citations with confidence='HIGH'.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_citation_confidence_low() -> None:
    """build_citations() assigns LOW confidence when source doc+page appears 1-2 times.

    Expected: a chunk list where a (filename, page_num) pair appears only once or
    twice produces citations with confidence='LOW'.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_format_answer_with_citations() -> None:
    """format_answer() appends a formatted citation table after the LLM response text.

    Expected: output string contains the original llm_response text followed by
    a 'Citations:' section listing each citation with index, filename, page, and confidence.
    """
    raise NotImplementedError
```

**tests/test_query_pipeline.py** (covers QUERY-01 and QUERY-05):
```python
"""Tests for src/query/pipeline.py — end-to-end query pipeline (QUERY-01, QUERY-05).

Stubs become passing once plan 04-04 implements answer_question().
LM Studio integration test is marked @pytest.mark.lm_studio — excluded from quick runs
via: pytest -k 'not lm_studio'
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_pipeline_end_to_end() -> None:
    """answer_question() returns dict with answer, citations, and elapsed_s.

    LM Studio is mocked (unittest.mock.patch). Expected: result dict has keys
    'answer' (non-empty str), 'citations' (list), 'elapsed_s' (float >= 0).
    Uses chromadb.EphemeralClient() and tempfile.mkdtemp() KuzuDB.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_pipeline_no_results() -> None:
    """answer_question() handles empty corpus gracefully (no chunks in ChromaDB).

    Expected: returns dict with answer indicating no information found;
    citations is an empty list; does not raise an exception.
    """
    raise NotImplementedError


@pytest.mark.lm_studio
@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_lm_studio_integration() -> None:
    """answer_question() produces a real answer via LM Studio (Qwen2.5-7B-Instruct).

    Requires LM Studio running at localhost:1234 with Qwen2.5-7B-Instruct loaded.
    Skip with: pytest -k 'not lm_studio'
    Expected: answer is a non-empty string; elapsed_s < 15.0.
    """
    raise NotImplementedError
```
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -m pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio" 2>&1 | tail -5</automated>
  </verify>

  <done>All 11 xfail stubs collected without errors; pytest reports xfailed (not ERROR); -k "not lm_studio" excludes the integration test correctly</done>
</task>

</tasks>

<verification>
```bash
# All stubs collect and report xfail (not import errors)
pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio"

# Imports clean
python -c "
from src.query.retriever import hybrid_retrieve, vector_search, graph_expand, deduplicate_chunks
from src.query.assembler import truncate_to_budget, build_citations, format_answer, build_prompt, CONTEXT_TOKEN_BUDGET
from src.query.pipeline import answer_question
print('All query imports OK')
"

# lm_studio marker registered (no PytestUnknownMarkWarning)
pytest tests/test_query_pipeline.py -q 2>&1 | grep -v "warning\|Warning" | tail -5

# Full suite unaffected
pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- pytest collects all 11 xfail stubs across 3 test files without import errors or collection errors
- pytest -k "not lm_studio" excludes test_lm_studio_integration cleanly (10 stubs collected)
- All 4 src/query/*.py stubs importable: python -c "from src.query.pipeline import answer_question" exits 0
- conftest.py registers lm_studio marker — no PytestUnknownMarkWarning in output
- Full prior test suite still green: pytest tests/ -x -q -k "not lm_studio" exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/04-query-engine-answer-generation/04-01-SUMMARY.md`
</output>
