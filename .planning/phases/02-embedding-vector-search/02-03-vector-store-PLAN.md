---
phase: 02-embedding-vector-search
plan: 03
type: execute
wave: 2
depends_on:
  - "02-01"
files_modified:
  - src/embed/vector_store.py
autonomous: true
requirements:
  - EMBED-02
  - EMBED-03

must_haves:
  truths:
    - "VectorStore.upsert() stores embeddings and all 5 metadata fields without raising"
    - "VectorStore.query() returns list of dicts with keys: chunk_id, text, metadata, distance"
    - "VectorStore.query() guards against NotEnoughElementsException by using min(n_results, count)"
    - "VectorStore.query() returns metadata dicts with filename and page_num for citation"
    - "VectorStore is instantiable with just a path string: VectorStore('data/chroma_db')"
  artifacts:
    - path: "src/embed/vector_store.py"
      provides: "VectorStore class wrapping ChromaDB PersistentClient"
      exports:
        - "VectorStore"
  key_links:
    - from: "src/embed/vector_store.py"
      to: "chromadb.PersistentClient"
      via: "__init__ creates client and collection"
      pattern: "chromadb\\.PersistentClient"
    - from: "src/embed/vector_store.py"
      to: "collection.upsert"
      via: "VectorStore.upsert() method"
      pattern: "collection\\.upsert"
    - from: "src/embed/vector_store.py"
      to: "collection.query"
      via: "VectorStore.query() method with count guard"
      pattern: "collection\\.count\\(\\)"
---

<objective>
Implement src/embed/vector_store.py — the ChromaDB wrapper class.

Provides VectorStore with upsert() (idempotent embed storage) and query() (top-N
semantic search). Uses chromadb.PersistentClient for production and supports
chromadb.EphemeralClient injection in tests via the _collection bypass pattern
already established in the xfail stubs.

Purpose: EMBED-02 + EMBED-03 — ChromaDB stores embeddings; metadata (filename, page_num,
chunk_index, doc_id, token_count) is co-located with vectors so Phase 4 can build
citations without a second SQLite lookup.

Output: src/embed/vector_store.py (replaces NotImplementedError stub)
</objective>

<execution_context>
@/Users/2171176/.claude/get-shit-done/workflows/execute-plan.md
@/Users/2171176/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-embedding-vector-search/02-RESEARCH.md
@.planning/phases/02-embedding-vector-search/02-01-SUMMARY.md

@src/embed/vector_store.py
</context>

<interfaces>
<!-- ChromaDB 1.5.5 verified API — from RESEARCH.md -->

```python
import chromadb

# Production
client = chromadb.PersistentClient(path="data/chroma_db")

# Test (no disk I/O, auto-GC)
client = chromadb.EphemeralClient()

# Collection with cosine distance — configuration only on first creation
collection = client.get_or_create_collection(
    name="chunks",
    configuration={"hnsw": {"space": "cosine"}},
)

# Upsert (idempotent — safe on crash recovery re-runs)
collection.upsert(
    ids=["1", "2"],                        # str — chunk_id as string
    embeddings=[[0.1]*768, [0.2]*768],
    documents=["text1", "text2"],
    metadatas=[
        {"doc_id": 1, "filename": "a.pdf", "page_num": 1, "chunk_index": 0, "token_count": 400},
        {"doc_id": 1, "filename": "a.pdf", "page_num": 2, "chunk_index": 1, "token_count": 380},
    ],
)

# Count guard (prevents NotEnoughElementsException)
count = collection.count()

# Query
results = collection.query(
    query_embeddings=[[0.15]*768],
    n_results=10,                          # must be <= collection.count()
    include=["documents", "metadatas", "distances"],
)
# results["ids"][0]        list[str]
# results["documents"][0]  list[str]
# results["metadatas"][0]  list[dict]
# results["distances"][0]  list[float] — cosine distance (0=identical, 2=opposite)
```

CRITICAL anti-patterns from RESEARCH.md:
- Do NOT use `collection.add()` — use `upsert()` for idempotency
- Do NOT pass `configuration` on every call — ChromaDB persists it after creation;
  re-passing a conflicting value raises an error. Pass configuration only once at creation.
- Do NOT skip `min(n_results, collection.count())` guard — raises NotEnoughElementsException
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement VectorStore class in src/embed/vector_store.py</name>

  <read_first>
    - src/embed/vector_store.py (current stub — read ALL method signatures to match exactly)
    - tests/test_embedding.py (read ALL vector_store tests: test_vector_store_upsert,
      test_vector_store_query_returns_n_results, test_vector_store_query_small_collection,
      test_vector_store_metadata_fields, test_vector_store_metadata_retrievable,
      test_query_latency_under_50ms — note the _collection bypass pattern used in tests)
    - .planning/phases/02-embedding-vector-search/02-RESEARCH.md (ChromaDB API Reference section,
      especially the configuration persistence note and anti-patterns)
  </read_first>

  <files>src/embed/vector_store.py</files>

  <behavior>
    - test_vector_store_upsert: after upsert(chunk_ids=[1,2], embeddings=..., documents=..., metadatas=[...]), vs.count() == 2
    - test_vector_store_query_returns_n_results: collection has 5 items, query(n_results=3) returns exactly 3 dicts
    - test_vector_store_query_small_collection: collection has 1 item, query(n_results=10) returns 1 dict (no exception)
    - test_vector_store_metadata_fields: upserted metadata dict with 5 keys is retrievable via collection.get(ids=["42"])
    - test_vector_store_metadata_retrievable: query result dict has key "metadata" with "filename" and "page_num"
    - test_query_latency_under_50ms: query on 100-item collection completes in < 50ms
  </behavior>

  <action>
Replace the NotImplementedError stub in src/embed/vector_store.py with the full implementation.

Implementation rules:

1. __init__(self, chroma_path: str = "data/chroma_db") -> None:
   - Create PersistentClient: `self._client = chromadb.PersistentClient(path=chroma_path)`
   - Create/get collection with cosine space. Use a try/except to handle the
     "configuration already set" edge case in ChromaDB 1.5.5+:
     ```python
     try:
         self._collection = self._client.get_or_create_collection(
             name="chunks",
             configuration={"hnsw": {"space": "cosine"}},
         )
     except Exception:
         # Collection exists with configuration already persisted
         self._collection = self._client.get_collection(name="chunks")
     ```
   - Store both as instance attributes.

2. upsert(self, chunk_ids, embeddings, documents, metadatas) -> None:
   - Convert chunk_ids to strings: `ids = [str(cid) for cid in chunk_ids]`
   - Call: `self._collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)`
   - No return value.

3. query(self, query_embedding: list[float], n_results: int = 10) -> list[dict]:
   - Guard: `actual_n = min(n_results, self._collection.count())`
   - If actual_n == 0, return []
   - Call: `results = self._collection.query(query_embeddings=[query_embedding], n_results=actual_n, include=["documents", "metadatas", "distances"])`
   - Build and return list of dicts:
     ```python
     return [
         {
             "chunk_id": results["ids"][0][i],
             "text": results["documents"][0][i],
             "metadata": results["metadatas"][0][i],
             "distance": results["distances"][0][i],
         }
         for i in range(len(results["ids"][0]))
     ]
     ```

4. count(self) -> int:
   - Return: `return self._collection.count()`

Note for tests: The xfail stubs bypass __init__ using `VectorStore.__new__(VectorStore)` and
directly set `vs._collection`. Your implementation MUST use the attribute name `_collection`
(underscore prefix) — the tests depend on this exact name. Do NOT rename it.

The method signatures MUST match the stub exactly:
```python
def upsert(
    self,
    chunk_ids: list[int],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:

def query(
    self,
    query_embedding: list[float],
    n_results: int = 10,
) -> list[dict]:

def count(self) -> int:
```
  </action>

  <verify>
    <automated>cd C:/Users/2171176/Documents/Python/Knowledge_Graph_v2 && python -m pytest tests/test_embedding.py::test_vector_store_upsert tests/test_embedding.py::test_vector_store_query_returns_n_results tests/test_embedding.py::test_vector_store_query_small_collection tests/test_embedding.py::test_vector_store_metadata_fields tests/test_embedding.py::test_vector_store_metadata_retrievable tests/test_embedding.py::test_query_latency_under_50ms -v 2>&1 | tail -15</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_embedding.py::test_vector_store_upsert -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_vector_store_query_returns_n_results -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_vector_store_query_small_collection -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_vector_store_metadata_fields -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_vector_store_metadata_retrievable -v` exits 0 and shows PASSED
    - `pytest tests/test_embedding.py::test_query_latency_under_50ms -v` exits 0 and shows PASSED
    - `grep "raise NotImplementedError" src/embed/vector_store.py` exits 1 (no stubs remain)
    - `grep "_collection" src/embed/vector_store.py` exits 0 (attribute name correct)
    - `grep "collection\.upsert" src/embed/vector_store.py` exits 0
    - `grep "collection\.count()" src/embed/vector_store.py` exits 0 (guard present)
    - `python -m pytest tests/test_embedding.py -q -m "not integration"` exits 0 (no regressions)
  </acceptance_criteria>

  <done>
VectorStore implemented. 6 previously-xfail unit tests now PASSED.
Full test suite still exits 0.
  </done>
</task>

</tasks>

<verification>
```
pytest tests/test_embedding.py -q -m "not integration"
```
Expected: 9 passed (3 from Plan 02 + 6 from Plan 03) + 2 xfailed (pipeline tests, implemented in Plan 04), exit code 0.

```
python -c "
import chromadb
from src.embed.vector_store import VectorStore
vs = VectorStore.__new__(VectorStore)
vs._collection = chromadb.EphemeralClient().get_or_create_collection('t', configuration={'hnsw':{'space':'cosine'}})
vs.upsert([1], [[0.1]*768], ['hello'], [{'doc_id':1,'filename':'a.pdf','page_num':1,'chunk_index':0,'token_count':10}])
r = vs.query([0.1]*768, n_results=1)
assert r[0]['metadata']['filename'] == 'a.pdf'
print('VectorStore OK')
"
```
</verification>

<success_criteria>
- VectorStore.__init__ creates PersistentClient and cosine collection
- upsert() stores embeddings with all 5 required metadata fields
- query() returns list[dict] with chunk_id, text, metadata, distance keys
- query() guard prevents NotEnoughElementsException
- 6 previously-xfail unit tests now PASSED
- No other tests regressed
</success_criteria>

<output>
After completion, create `.planning/phases/02-embedding-vector-search/02-03-SUMMARY.md`
</output>
