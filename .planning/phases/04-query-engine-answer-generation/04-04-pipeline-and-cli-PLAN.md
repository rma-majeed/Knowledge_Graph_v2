---
phase: 04-query-engine-answer-generation
plan: 04
type: execute
wave: 3
depends_on:
  - "04-02"
  - "04-03"
files_modified:
  - src/query/pipeline.py
  - src/main.py
autonomous: false
requirements:
  - QUERY-01
  - QUERY-05

must_haves:
  truths:
    - "answer_question() wires hybrid_retrieve() -> truncate_to_budget() -> build_prompt() -> LM Studio LLM -> format_answer() -> build_citations(); returns dict with keys answer, citations, elapsed_s"
    - "python src/main.py query --question 'What EV strategies did Toyota adopt?' prints a synthesized answer and citation table"
    - "python src/main.py query --help shows --question, --db, --chroma, --graph, --embed-model, --llm-model, --top-k arguments"
    - "python src/main.py --help still shows ingest, stats, embed, graph, query subcommands"
    - "test_query_pipeline.py end-to-end and no-results tests pass with mocked LM Studio (not xfail)"
    - "Query latency measured and printed: elapsed_s displayed to user after answer"
  artifacts:
    - path: "src/query/pipeline.py"
      provides: "answer_question() orchestration function"
      exports:
        - answer_question
        - DEFAULT_LLM_MODEL
        - DEFAULT_EMBED_MODEL
      min_lines: 60
    - path: "src/main.py"
      provides: "query subcommand wired to answer_question()"
      contains: "cmd_query"
  key_links:
    - from: "src/query/pipeline.py"
      to: "src/query/retriever.py"
      via: "hybrid_retrieve(question, openai_client, conn, kuzu_db, chroma_path, embed_model, n_results)"
      pattern: "from src.query.retriever import hybrid_retrieve"
    - from: "src/query/pipeline.py"
      to: "src/query/assembler.py"
      via: "truncate_to_budget(chunks) -> build_prompt(question, context_str) -> build_citations(included)"
      pattern: "from src.query.assembler import"
    - from: "src/main.py"
      to: "src/query/pipeline.py"
      via: "from src.query.pipeline import answer_question"
      pattern: "from src.query.pipeline import answer_question"
    - from: "src/main.py"
      to: "src/embed/pipeline.py"
      via: "check_lm_studio() health check before query"
      pattern: "from src.embed.pipeline import check_lm_studio"
---

<objective>
Implement `src/query/pipeline.py` (answer_question orchestrator) and add the `query` subcommand to `src/main.py`.

Purpose: This is the integration plan that wires retriever and assembler into a single callable pipeline and exposes it via CLI. Mirrors the pattern established by plan 03-05 (build_knowledge_graph + graph subcommand) exactly.

Output: `src/query/pipeline.py` with `answer_question()`; `src/main.py` updated with `cmd_query()` and `query` subparser; human checkpoint verifies end-to-end CLI execution.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-query-engine-answer-generation/04-RESEARCH.md
@.planning/phases/04-query-engine-answer-generation/04-02-SUMMARY.md
@.planning/phases/04-query-engine-answer-generation/04-03-SUMMARY.md

<interfaces>
<!-- src/query/retriever.py — hybrid_retrieve() signature (from plan 04-02) -->
```python
def hybrid_retrieve(
    query_text: str,
    openai_client,
    sqlite_conn,
    kuzu_db,
    chroma_path: str = "data/chroma_db",
    embed_model: str = "nomic-embed-text-v1.5",
    n_results: int = 10,
) -> list[dict]:
    """Returns deduplicated list of chunk dicts with source='vector' or source='graph'."""
```

<!-- src/query/assembler.py — pipeline call sequence (from plan 04-03) -->
```python
from src.query.assembler import truncate_to_budget, build_citations, format_answer, build_prompt

context_str, included_chunks = truncate_to_budget(chunks)
messages = build_prompt(question, context_str)
# ... LM Studio call ...
citations = build_citations(included_chunks)
final_answer = format_answer(llm_response, citations)
```

<!-- LM Studio LLM call pattern (matches extractor.py from Phase 3) -->
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
response = client.chat.completions.create(
    model=llm_model,
    messages=messages,   # from build_prompt()
    temperature=0.2,
    max_tokens=600,
)
llm_response = response.choices[0].message.content.strip()
```

<!-- src/embed/pipeline.py — check_lm_studio() (reuse, do not re-implement) -->
```python
def check_lm_studio() -> bool:
    """Returns True if LM Studio is reachable at localhost:1234."""
```

<!-- src/main.py — cmd_graph() pattern to replicate for cmd_query() -->
def cmd_graph(args: argparse.Namespace) -> int:
    # 1. Validate paths (db must exist)
    # 2. check_lm_studio() health check, exit 1 with clear message if down
    # 3. Open sqlite3.connect(db_path), conn.row_factory = sqlite3.Row
    # 4. Open kuzu.Database(graph_path)
    # 5. Call pipeline function in try/finally block
    # 6. Print summary, close conn in finally

<!-- answer_question() return dict shape -->
{
    "answer": str,          # formatted answer with inline [N] citations
    "citations": list[dict],  # [{index, filename, page_num, confidence, source}, ...]
    "elapsed_s": float,     # total wall-clock seconds for retrieve+generate
}
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement src/query/pipeline.py with answer_question()</name>
  <files>src/query/pipeline.py, tests/test_query_pipeline.py</files>

  <read_first>
    - src/query/pipeline.py (current stub — replace NotImplementedError)
    - tests/test_query_pipeline.py (current xfail stubs — remove xfail for end-to-end and no-results tests)
    - src/graph/pipeline.py (build_knowledge_graph — replicate the openai_client creation pattern and try/except error handling)
    - .planning/phases/04-query-engine-answer-generation/04-RESEARCH.md (Pattern 6 cmd_query code block and anti-patterns section on stateless messages list)
  </read_first>

  <action>
Implement `src/query/pipeline.py` replacing the NotImplementedError stub. The function must be stateless — it creates a fresh OpenAI client per call and constructs a fresh messages list per query (never accumulates history).

```python
"""Query pipeline: hybrid retrieval + context assembly + LM Studio answer generation.

Wires together:
  hybrid_retrieve()   — src/query/retriever.py (vector + graph)
  truncate_to_budget() — src/query/assembler.py (token budget)
  build_prompt()       — src/query/assembler.py (system + user messages)
  LM Studio LLM call   — openai.OpenAI(base_url="http://localhost:1234/v1")
  format_answer()      — src/query/assembler.py (append citation table)
  build_citations()    — src/query/assembler.py (HIGH/LOW confidence)

Usage:
    import sqlite3, kuzu
    from src.query.pipeline import answer_question

    conn = sqlite3.connect("data/chunks.db")
    conn.row_factory = sqlite3.Row
    db = kuzu.Database("data/kuzu_db")
    result = answer_question("What EV strategies did Toyota adopt?", conn, db)
    print(result["answer"])
"""
from __future__ import annotations

import time
import sqlite3
import kuzu

DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"
_LLM_MAX_TOKENS = 600
_LLM_TEMPERATURE = 0.2


def answer_question(
    question: str,
    conn: sqlite3.Connection,
    kuzu_db: kuzu.Database,
    chroma_path: str = "data/chroma_db",
    embed_model: str = DEFAULT_EMBED_MODEL,
    llm_model: str = DEFAULT_LLM_MODEL,
    n_results: int = 10,
    openai_client=None,
) -> dict:
    """Run hybrid retrieval + LM Studio answer generation for a natural language question.

    Args:
        question: Natural language question from the consultant.
        conn: Open sqlite3.Connection (row_factory=sqlite3.Row set by caller).
        kuzu_db: Open kuzu.Database for graph traversal.
        chroma_path: Path to ChromaDB persistence directory.
        embed_model: LM Studio embedding model name (must be loaded when calling).
        llm_model: LM Studio LLM model name (must be loaded for generation step).
        n_results: Number of vector results before graph expansion.
        openai_client: openai.OpenAI client. Created automatically if None.

    Returns:
        Dict with keys:
        - answer (str): Formatted answer with inline [N] citations and citation table
        - citations (list[dict]): [{index, filename, page_num, confidence, source}, ...]
        - elapsed_s (float): Total wall-clock seconds for retrieve + generate
    """
    from openai import OpenAI
    from src.query.retriever import hybrid_retrieve
    from src.query.assembler import (
        truncate_to_budget, build_citations, format_answer, build_prompt
    )

    if openai_client is None:
        openai_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    start = time.perf_counter()

    # Step 1: Hybrid retrieval (vector + 1-hop graph expansion)
    chunks = hybrid_retrieve(
        query_text=question,
        openai_client=openai_client,
        sqlite_conn=conn,
        kuzu_db=kuzu_db,
        chroma_path=chroma_path,
        embed_model=embed_model,
        n_results=n_results,
    )

    # Step 2: Assemble context within token budget
    context_str, included_chunks = truncate_to_budget(chunks)

    # Step 3: Build prompt and call LM Studio LLM
    # Fresh messages list per call — never accumulate history (stateless pipeline)
    messages = build_prompt(question, context_str)

    if not included_chunks:
        llm_response = "The available documents do not contain sufficient information to answer this question."
    else:
        response = openai_client.chat.completions.create(
            model=llm_model,
            messages=messages,
            temperature=_LLM_TEMPERATURE,
            max_tokens=_LLM_MAX_TOKENS,
        )
        llm_response = response.choices[0].message.content.strip()

    # Step 4: Build citations and format final answer
    citations = build_citations(included_chunks)
    final_answer = format_answer(llm_response, citations)

    elapsed_s = time.perf_counter() - start

    return {
        "answer": final_answer,
        "citations": citations,
        "elapsed_s": elapsed_s,
    }
```

After implementing, update `tests/test_query_pipeline.py`:
- Remove `@pytest.mark.xfail` from `test_query_pipeline_end_to_end` and `test_query_pipeline_no_results`
- Keep `@pytest.mark.lm_studio` and `@pytest.mark.xfail` on `test_lm_studio_integration` — it remains an xfail until a real LM Studio session is used
- For `test_query_pipeline_end_to_end`: use `unittest.mock.patch("src.query.pipeline.answer_question")` pattern OR mock at `openai.OpenAI` level; use `chromadb.EphemeralClient()` and `tempfile.mkdtemp()` KuzuDB; assert result has keys "answer", "citations", "elapsed_s"
- For `test_query_pipeline_no_results`: mock `hybrid_retrieve` to return []; assert answer contains "not contain sufficient information"; assert citations == []
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -m pytest tests/test_query_pipeline.py -x -q -k "not lm_studio" --tb=short 2>&1 | tail -8</automated>
  </verify>

  <done>test_query_pipeline_end_to_end and test_query_pipeline_no_results pass (not xfail); answer_question() importable; pipeline.py contains no NotImplementedError</done>
</task>

<task type="auto">
  <name>Task 2: Add query subcommand to src/main.py</name>
  <files>src/main.py</files>

  <read_first>
    - src/main.py (entire file — understand current cmd_graph() structure to add cmd_query() without breaking existing subcommands)
    - src/query/pipeline.py (answer_question signature — match arg names to argparse defaults)
    - .planning/phases/04-query-engine-answer-generation/04-RESEARCH.md (Pattern 6 cmd_query code block — use verbatim)
  </read_first>

  <action>
Read `src/main.py` completely first. Add `cmd_query()` after `cmd_graph()` and add the `query` subcommand parser in `main()`.

1. Add `cmd_query()` function after `cmd_graph()`:

```python
def cmd_query(args: argparse.Namespace) -> int:
    """Run the query pipeline and print answer + citations."""
    import sqlite3
    import kuzu
    from src.embed.pipeline import check_lm_studio
    from src.query.pipeline import answer_question

    db_path = Path(args.db)
    graph_path = Path(args.graph)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    if not graph_path.exists():
        print(f"Error: KuzuDB not found: {graph_path}", file=sys.stderr)
        return 1

    if not check_lm_studio():
        print(
            "Error: LM Studio is not running at localhost:1234.\n"
            "Ensure LM Studio is running. For query, load the LLM model\n"
            f"({args.llm_model}) — not the embedding model.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    db = kuzu.Database(str(graph_path))

    try:
        result = answer_question(
            question=args.question,
            conn=conn,
            kuzu_db=db,
            chroma_path=str(chroma_path),
            embed_model=args.embed_model,
            llm_model=args.llm_model,
            n_results=args.top_k,
        )
        print(f"\n{result['answer']}\n")
        elapsed = result.get("elapsed_s", 0.0)
        print(f"Query completed in {elapsed:.1f}s")
    finally:
        conn.close()

    return 0
```

2. Add `query` subcommand parser in `main()` after the `graph` subcommand block:

```python
    # query subcommand
    p_query = subparsers.add_parser("query", help="Answer a natural language question")
    p_query.add_argument(
        "--question", required=True,
        help="Natural language question to answer"
    )
    p_query.add_argument(
        "--db", default="data/chunks.db",
        help="SQLite database path (default: data/chunks.db)"
    )
    p_query.add_argument(
        "--chroma", default="data/chroma_db",
        help="ChromaDB path (default: data/chroma_db)"
    )
    p_query.add_argument(
        "--graph", default="data/kuzu_db",
        help="KuzuDB directory path (default: data/kuzu_db)"
    )
    p_query.add_argument(
        "--embed-model", default="nomic-embed-text-v1.5",
        dest="embed_model",
        help="LM Studio embedding model (default: nomic-embed-text-v1.5)"
    )
    p_query.add_argument(
        "--llm-model", default="Qwen2.5-7B-Instruct",
        dest="llm_model",
        help="LM Studio LLM model for answer generation (default: Qwen2.5-7B-Instruct)"
    )
    p_query.add_argument(
        "--top-k", type=int, default=10,
        dest="top_k",
        help="Number of vector results before graph expansion (default: 10)"
    )
    p_query.set_defaults(func=cmd_query)
```
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python src/main.py --help 2>&1 | grep -E "ingest|stats|embed|graph|query" && python src/main.py query --help 2>&1 | grep -E "\-\-question|\-\-db|\-\-chroma|\-\-graph|\-\-llm-model|\-\-top-k"</automated>
  </verify>

  <done>cmd_query() added; query subcommand registered with all 7 arguments; python src/main.py --help shows all 5 subcommands; existing subcommands unaffected</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Complete Phase 4 query pipeline:
    - src/query/retriever.py — vector_search + graph_expand + hybrid_retrieve
    - src/query/assembler.py — truncate_to_budget + build_citations + format_answer + build_prompt
    - src/query/pipeline.py — answer_question() end-to-end orchestration
    - src/main.py — query CLI subcommand with 7 arguments
    - All 10 query stubs now GREEN across 3 test files (lm_studio integration remains xfail)
  </what-built>

  <how-to-verify>
1. Run the full test suite (must be all green):
   ```
   pytest tests/ -x -q -k "not lm_studio" --tb=short
   ```
   Expected: All tests pass. Query stubs (test_query_retriever, test_query_assembler, test_query_pipeline end-to-end and no-results) are GREEN. lm_studio integration test is xfail — that is correct.

2. Verify CLI help works:
   ```
   python src/main.py --help
   python src/main.py query --help
   ```
   Expected: `--help` lists all 5 subcommands (ingest, stats, embed, graph, query). `query --help` shows --question, --db, --chroma, --graph, --embed-model, --llm-model, --top-k.

3. Verify all src/query modules import cleanly:
   ```
   python -c "
   from src.query.retriever import hybrid_retrieve
   from src.query.assembler import truncate_to_budget, build_citations, CONTEXT_TOKEN_BUDGET
   from src.query.pipeline import answer_question
   print('All query imports OK')
   "
   ```

4. (Optional — requires LM Studio with Qwen2.5-7B-Instruct loaded):
   If LM Studio is running with Qwen2.5-7B-Instruct:
   ```
   python src/main.py query --question "What EV battery technologies appear in our consulting documents?" --db data/chunks.db --chroma data/chroma_db --graph data/kuzu_db
   ```
   Expected: Prints a synthesized answer followed by a Citations section and "Query completed in X.Xs". Latency should be under 15 seconds.
  </how-to-verify>

  <resume-signal>Type "approved" when all automated checks pass and imports are clean. Describe any failures if checks do not pass.</resume-signal>
</task>

</tasks>

<verification>
```bash
# All query tests pass (10 tests GREEN; lm_studio xfail is expected)
pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -v -k "not lm_studio" --tb=short

# Full suite green
pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5

# CLI help
python src/main.py --help
python src/main.py query --help

# All imports
python -c "
from src.query.retriever import hybrid_retrieve
from src.query.assembler import truncate_to_budget, build_citations, CONTEXT_TOKEN_BUDGET
from src.query.pipeline import answer_question
print('All OK')
"
```
</verification>

<success_criteria>
- answer_question() wires hybrid_retrieve -> truncate_to_budget -> build_prompt -> LLM -> format_answer; returns {answer, citations, elapsed_s}
- python src/main.py query --help shows all 7 arguments
- python src/main.py --help shows all 5 subcommands (ingest, stats, embed, graph, query)
- Full test suite green: pytest tests/ -x -q -k "not lm_studio" exits 0
- test_query_pipeline end-to-end and no-results PASS; lm_studio integration test stays xfail until live LM Studio test
- Human checkpoint approved
</success_criteria>

<output>
After completion, create `.planning/phases/04-query-engine-answer-generation/04-04-SUMMARY.md`
</output>
