# Phase 6: Multi-Provider LLM & Embedding Configuration - Research

**Researched:** 2026-03-31
**Domain:** LLM provider abstraction, environment variable configuration, LiteLLM integration
**Confidence:** HIGH

## Summary

Phase 6 makes all LLM and embedding provider choices configurable via `.env` file using LiteLLM as a universal adapter. Currently, the codebase hardcodes OpenAI clients pointing to LM Studio (`base_url="http://localhost:1234/v1"`). This phase abstracts that away so any user can swap providers (LM Studio, Ollama, Gemini, OpenAI, Anthropic) without code changes — only by editing `.env`.

The core insight: LiteLLM's `openai/` prefix for OpenAI-compatible endpoints allows seamless routing of identical code to different backends. Default behavior (LM Studio) remains unchanged when `.env` is absent. Embedding provider switches are safeguarded via a reindexing warning.

**Primary recommendation:** Use LiteLLM with `python-dotenv` for standard Python patterns; route all LLM/embedding calls through a provider factory function; keep existing hardcoded LM Studio instantiation as fallback when .env is absent.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROVIDER-01 | Read LLM provider config from .env; default to LM Studio if absent | `.env` file reading strategy covered; python-dotenv is standard, zero-weight option |
| PROVIDER-02 | Support LM Studio, Ollama, Gemini, OpenAI, Anthropic via LiteLLM | LiteLLM docs confirm all 5 supported for chat/completions with openai/ prefix |
| PROVIDER-03 | Read embedding provider config from .env; default to LM Studio if absent | LiteLLM embedding() supports OpenAI-compatible endpoints; embeddings via openai/ prefix |
| PROVIDER-04 | Support LM Studio, Ollama, Gemini, OpenAI as embedding providers | LiteLLM embedding docs show openai/ prefix works for all 4; Ollama tested, Gemini/OpenAI verified |
| PROVIDER-05 | Changing LLM provider requires only .env update, no code changes | LiteLLM factory pattern + python-dotenv eliminates code coupling |
| PROVIDER-06 | Embedding provider switch warns user re-embed is required | Warning logic added to embed pipeline on provider mismatch detection |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | Latest (1.45+) | Universal LLM/embedding adapter (100+ providers via single API) | Open-source, pip-installable, zero-weight abstraction, supports all required providers + streaming |
| python-dotenv | Latest (1.0+) | Load .env file into environment variables | Standard Python convention, zero dependencies, used by Django/FastAPI communities |
| openai | 1.0+ (already installed) | OpenAI client library (LiteLLM uses this under the hood) | Already a dependency; LiteLLM wraps it for multi-provider routing |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.24+ (already installed) | HTTP client for OpenAI-compatible servers | Already installed; LiteLLM and embedding client use it; supports timeouts/retries |

### Installation

```bash
pip install litellm python-dotenv
```

Version verification (as of 2026-03-31):
- **litellm:** v1.45+ (LiteLLM PyPI https://pypi.org/project/litellm/)
- **python-dotenv:** v1.0+ (PyPI https://pypi.org/project/python-dotenv/)

Both are lightweight, single-file-deployable packages. LiteLLM's only hard dependencies are httpx and openai (both already installed).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LiteLLM | pydantic-ai / instructor / other client libs | Would require separate implementations per provider; LiteLLM handles 100+ in one pattern |
| python-dotenv | Manual os.environ reading / configparser | Possible but less Pythonic; python-dotenv is industry standard for dev .env files |
| OpenAI client as fallback | Strict LiteLLM-only routing | Current hardcoded OpenAI client serves as good fallback when .env absent; minimizes changes |

## Architecture Patterns

### Recommended Project Structure

No new directories required. Existing structure:

```
app.py                           # Streamlit UI — calls get_llm_client()
src/
├── embed/
│   ├── embedder.py            # embed_chunks(), embed_query() — calls get_embed_client()
│   └── pipeline.py            # embed_all_chunks() — calls get_embed_client()
├── graph/
│   ├── extractor.py           # extract_entities_relationships() — calls get_llm_client()
│   └── pipeline.py            # build_knowledge_graph() — calls get_llm_client()
├── query/
│   ├── retriever.py           # hybrid_retrieve() — calls get_embed_client() for query embedding
│   └── pipeline.py            # answer_question() — calls get_llm_client() for generation
├── config/                      # NEW: provider configuration
│   ├── __init__.py
│   └── providers.py            # get_llm_client(), get_embed_client(), load_provider_config()
data/
├── .env                         # NEW: provider settings (git-ignored)
└── .env.example                 # NEW: template (in git)
```

### Pattern 1: Provider Factory Functions

**What:** Centralized functions that instantiate and return configured LLM/embedding clients based on .env variables.

**When to use:** Every pipeline that calls LLM APIs or embedding models should obtain its client from these factories, never instantiate clients directly.

**Example:**

```python
# src/config/providers.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env once at module import time
_ENV_LOADED = False
def _ensure_env_loaded():
    global _ENV_LOADED
    if not _ENV_LOADED:
        dotenv_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(dotenv_path)
        _ENV_LOADED = True

def get_llm_client():
    """Return configured LLM client (LiteLLM or OpenAI fallback).

    Respects .env variables:
    - LLM_PROVIDER: 'lm-studio' (default), 'ollama', 'gemini', 'openai', 'anthropic'
    - LLM_MODEL: model name (required if provider != lm-studio)
    - LLM_API_KEY: API key (required for cloud providers)
    - LLM_API_BASE: base URL for OpenAI-compatible servers (optional, defaults to localhost:1234)
    """
    _ensure_env_loaded()

    provider = os.getenv("LLM_PROVIDER", "lm-studio").lower()

    # Fallback: hardcoded LM Studio for backward compatibility
    if provider == "lm-studio":
        from openai import OpenAI
        return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    # LiteLLM routing for cloud providers
    import litellm

    api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
    model = os.getenv(f"{provider.upper()}_MODEL", "")
    api_base = os.getenv("LLM_API_BASE", None)

    if not model:
        raise ValueError(f"LLM_MODEL or {provider.upper()}_MODEL not set in .env")
    if provider != "ollama" and not api_key:
        raise ValueError(f"{provider.upper()}_API_KEY not set in .env")

    # Return LiteLLM completion client (litellm.completion / litellm.chat.completions.create)
    return litellm.LiteLLMClient(
        api_key=api_key,
        model=model,
        api_base=api_base,
    )

def get_embed_client():
    """Return configured embedding client.

    Respects .env variables:
    - EMBED_PROVIDER: 'lm-studio' (default), 'ollama', 'gemini', 'openai'
    - EMBED_MODEL: model name (required if provider != lm-studio)
    - EMBED_API_KEY: API key (required for cloud providers)
    - EMBED_API_BASE: base URL for OpenAI-compatible servers (optional, defaults to localhost:1234)
    """
    _ensure_env_loaded()

    provider = os.getenv("EMBED_PROVIDER", "lm-studio").lower()

    # Fallback: hardcoded LM Studio
    if provider == "lm-studio":
        from openai import OpenAI
        return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    # LiteLLM routing
    import litellm

    api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
    model = os.getenv(f"{provider.upper()}_MODEL", "")
    api_base = os.getenv("EMBED_API_BASE", None)

    if not model:
        raise ValueError(f"EMBED_MODEL or {provider.upper()}_MODEL not set in .env")
    if provider != "ollama" and not api_key:
        raise ValueError(f"{provider.upper()}_API_KEY not set in .env")

    return litellm.LiteLLMClient(
        api_key=api_key,
        model=model,
        api_base=api_base,
    )

def get_current_embed_provider() -> str:
    """Return current embedding provider name for config validation."""
    _ensure_env_loaded()
    return os.getenv("EMBED_PROVIDER", "lm-studio").lower()

def get_current_embed_model() -> str:
    """Return current embedding model name."""
    _ensure_env_loaded()
    provider = os.getenv("EMBED_PROVIDER", "lm-studio").lower()
    return os.getenv(f"EMBED_{provider.upper()}_MODEL",
                      os.getenv("EMBED_MODEL", "nomic-embed-text-v1.5"))
```

**Why this pattern:** Centralizes all provider config logic; makes it easy to add new providers; preserves backward compatibility with hardcoded fallback; passes `client` to pipelines without exposing how it was built.

### Pattern 2: Embedding Provider Mismatch Detection

**What:** Before running embedding, check if the current provider/model differs from what was used to build the existing ChromaDB. Warn and require user confirmation if so.

**When to use:** In `embed_all_chunks()` and via CLI before embedding starts.

**Example:**

```python
# src/embed/pipeline.py
def embed_all_chunks(conn, chroma_client, model, openai_client=None, ...):
    """..."""
    # NEW: Detect embedding provider mismatch
    current_provider = get_current_embed_provider()
    current_model = get_current_embed_model()

    # Check SQLite for stored embedding metadata
    stored_model = conn.execute(
        "SELECT embedding_model FROM metadata WHERE key='embedding_model' LIMIT 1"
    ).fetchone()

    if stored_model and stored_model[0] != current_model:
        print(
            f"\nWARNING: Embedding model changed from '{stored_model[0]}' to '{current_model}'.\n"
            f"Re-embedding will update all vectors. This may take a long time.\n"
            f"Proceed? (yes/no): "
        )
        if input().strip().lower() != "yes":
            print("Aborted.")
            return {"chunks_embedded": 0, "batches": 0}

    # ... rest of embedding logic

    # Store current model after successful embedding
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('embedding_model', ?)",
        (current_model,)
    )
    conn.commit()
```

### Anti-Patterns to Avoid

- **Direct OpenAI client instantiation in pipelines:** Hard to test, couples code to provider. Use factory instead.
- **Hardcoded API keys in code:** Never. All keys from .env or environment only.
- **Provider config scattered across multiple files:** Centralize in src/config/providers.py; other modules import from there.
- **Silent provider mismatches on embedding:** User loses historical embeddings without realizing. Always warn and require confirmation.
- **No fallback when .env is missing:** Keep the existing hardcoded LM Studio client as fallback for backward compatibility.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-provider LLM API routing | Custom provider-dispatch code | LiteLLM (100+ providers, streaming, retries, cost tracking) | Tested in production; handles edge cases (timeouts, auth retries) custom code would miss |
| Environment variable loading | Manual os.environ + parsing | python-dotenv (load_dotenv) | Standard Python convention; handles comments, quotes, multiline values; zero dependencies |
| Client instantiation per provider | Switch/if-else logic in pipelines | Provider factory pattern (get_llm_client, get_embed_client) | Single source of truth for config; testable; extensible for new providers |
| Embedding provider tracking | Manual string comparison | SQLite metadata table + mismatch check | Prevents silent data loss; persists across sessions |
| OpenAI client abstraction for non-OpenAI providers | Wrapper adapters | LiteLLM openai/ prefix routing | Identical code paths; LiteLLM handles model name normalization |

**Key insight:** LiteLLM's genius is that it implements the OpenAI API *exactly* — same parameter names, same response structure, same streaming protocol. This means existing code using `openai.OpenAI(...)` needs only a config change to route through LiteLLM, not a rewrite.

## Runtime State Inventory

**Trigger:** This is a configuration/integration phase, not a rename/refactor. No stored data, OS registrations, or build artifacts embed provider names. However, we DO need to track embedding model choice in the database.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | ChromaDB vectors: created with specific embedding model (e.g., nomic-embed-text-v1.5); metadata: no model tracking yet in SQLite | Schema change: add metadata table to track EMBED_PROVIDER + EMBED_MODEL; mismatch check on embed_all_chunks() |
| Live service config | LM Studio running on localhost:1234 (hardcoded in 4 files); no external service configs | Code change: replace hardcoded URLs with get_llm_client() / get_embed_client() calls; backward compat fallback when .env absent |
| OS-registered state | None | None — no system task schedules or launchers use provider names |
| Secrets/env vars | None currently stored in .env (first time) | Add to gitignore: `.env` (checked into git); commit: `.env.example` (template for users) |
| Build artifacts | None | None — no compiled binaries or pkg-info directories embed provider names |

## Common Pitfalls

### Pitfall 1: Provider Key Naming Mismatch
**What goes wrong:** User sets `OPENAI_API_KEY` in .env but code looks for `OPENAI_KEY`. Pipeline silently falls back to hardcoded LM Studio when it should use OpenAI.

**Why it happens:** No validation that required .env keys are present before instantiating client.

**How to avoid:**
- Document standardized variable names (PROVIDER_API_KEY, PROVIDER_MODEL, PROVIDER_API_BASE) in .env.example with comments.
- In get_llm_client() / get_embed_client(), validate all required keys before returning client; raise ValueError with clear message if missing.
- Test with mock .env files that have deliberately missing keys.

**Warning signs:** Provider set but client falls back to LM Studio; no error raised; user confused why their API key is ignored.

### Pitfall 2: Mixing OpenAI client and LiteLLM in same codebase
**What goes wrong:** Some pipelines use get_llm_client() (returns LiteLLM), others still directly instantiate OpenAI(). Code paths diverge; some features (streaming, retries) work in one, not the other.

**Why it happens:** Refactoring is gradual; old code with hardcoded clients is left in place alongside new factory code.

**How to avoid:**
- Replace all direct OpenAI instantiations with get_llm_client() / get_embed_client() calls.
- Search codebase for `OpenAI(base_url=` and `openai.OpenAI(` — should find only one: the fallback inside get_llm_client().
- Test all pipelines (embed, graph, query) with LiteLLM backend enabled.

**Warning signs:** Inconsistent behavior across pipelines; streaming works in one, not another; timeout configs lost.

### Pitfall 3: Silent embedding model mismatch
**What goes wrong:** User switches EMBED_MODEL in .env, re-runs embed. Old ChromaDB is silently used (vectors created with old model). New queries embed with new model, but retrieve against old vectors. Recall drops; user sees "garbage results" without understanding why.

**Why it happens:** No tracking of which embedding model created the vectors in ChromaDB. No warning when models mismatch.

**How to avoid:**
- Store embedding model name in SQLite metadata table when embedding completes.
- On next embed_all_chunks() call, fetch stored model; compare to current EMBED_MODEL.
- If mismatch: warn user, require "yes" confirmation, OR auto-delete ChromaDB and start fresh.
- Document clearly: "Switching embedding models requires full re-embedding."

**Warning signs:** User reports degraded search quality after changing EMBED_MODEL; downstream queries fail silently.

### Pitfall 4: API_BASE URL trailing slash inconsistency
**What goes wrong:** User sets `LLM_API_BASE=http://localhost:8000/v1` (with trailing slash). LiteLLM appends /v1 again, resulting in `http://localhost:8000/v1/v1`. 404 errors.

**Why it happens:** OpenAI docs say api_base should be base URL (no /v1); LiteLLM also appends /v1 for compatibility. But user documentation is unclear.

**How to avoid:**
- In .env.example, show CORRECT format: `LLM_API_BASE=http://localhost:8000` (no /v1).
- In get_llm_client(), validate api_base does NOT end with /v1; strip if present with warning.
- Test with both `localhost:8000` and `localhost:8000/v1` in .env; verify correct endpoint is called.

**Warning signs:** LiteLLM raises 404 or connection errors on model calls; user sees "invalid endpoint" in logs.

### Pitfall 5: Hardcoded LM Studio fallback never tested
**What goes wrong:** Fallback code (hardcoded LM Studio client in get_llm_client() when LLM_PROVIDER absent) is never executed in normal testing. It breaks silently when .env is missing.

**Why it happens:** Tests always mock the client or set LLM_PROVIDER. Real users forget to create .env file. Backward compat code is untested.

**How to avoid:**
- Write unit test: test_llm_client_fallback_without_env() — delete/rename .env file, call get_llm_client(), verify it returns hardcoded LM Studio client.
- Same for embedding: test_embed_client_fallback_without_env().
- Run these tests regularly; do NOT skip them.

**Warning signs:** .env file missing or misconfigured; app works for some users, fails for others; no error message (falls back silently).

## Code Examples

Verified patterns from official sources:

### LLM Completion with LiteLLM (all providers, identical code)

```python
# Source: https://docs.litellm.ai/docs/
from litellm import completion

response = completion(
    model="gpt-3.5-turbo",  # OpenAI
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(response.choices[0].message.content)
```

**For LM Studio:**
```python
response = completion(
    model="openai/local-model",  # openai/ prefix routes to custom api_base
    messages=[{"role": "user", "content": "..."}],
    api_base="http://localhost:1234/v1",
    api_key="lm-studio",
)
```

**For Ollama:**
```python
response = completion(
    model="openai/llama2",  # openai/ prefix for OpenAI-compatible endpoint
    messages=[{"role": "user", "content": "..."}],
    api_base="http://localhost:11434/v1",  # Ollama OpenAI-compat endpoint
    api_key="ollama",  # dummy key
)
```

All return identical response objects; same streaming parameter.

### Embeddings with LiteLLM (OpenAI-compatible endpoint)

```python
# Source: https://docs.litellm.ai/docs/embedding/supported_embedding
from litellm import embedding

response = embedding(
    model="openai/nomic-embed-text",  # openai/ prefix for OAI-compatible server
    input=["hello world"],
    api_base="http://localhost:1234/v1",
    api_key="lm-studio",
)
print(response.data[0].embedding)  # list[float]
```

**Streaming completions (all providers):**
```python
response = completion(
    model="openai/qwen2.5",
    messages=[{"role": "user", "content": "..."}],
    api_base="http://localhost:1234/v1",
    api_key="lm-studio",
    stream=True,  # streaming
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Loading .env with python-dotenv

```python
# Source: https://github.com/theskumar/python-dotenv
from dotenv import load_dotenv
import os

# Load .env file from disk
load_dotenv(".env")

# Access variables as normal os.environ
api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-4")  # default if not set
```

### Testing with LiteLLM mock_response

```python
# Source: https://docs.litellm.ai/docs/completion/mock_requests
from litellm import completion

# No API call; returns mocked response
response = completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Why is LiteLLM awesome?"}],
    mock_response="LiteLLM is awesome because it supports 100+ LLM providers with a single API!",
)

assert response.choices[0].message.content == "LiteLLM is awesome because it supports 100+ LLM providers with a single API!"
```

**Pytest pattern with monkeypatch (for testing embed/LLM calls):**

```python
import pytest
from unittest.mock import MagicMock, patch

def test_embed_chunks_with_mock(monkeypatch):
    """Test embed_chunks without calling actual LM Studio."""
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[
            MagicMock(embedding=[0.1] * 768),
            MagicMock(embedding=[0.2] * 768),
        ]
    )

    from src.embed.embedder import embed_chunks

    chunks = [
        {"chunk_text": "hello"},
        {"chunk_text": "world"},
    ]

    result = embed_chunks(chunks, mock_client, "nomic-embed-text")
    assert len(result) == 2
    assert len(result[0]) == 768
    assert result[0] == [0.1] * 768
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded OpenAI client per provider | Single LiteLLM abstraction with openai/ prefix routing | 2020–2023 emergence of OpenAI-compatible APIs | No need to write provider-specific code; add new providers via config only |
| Manual environment variable reading (os.environ + parsing) | python-dotenv + load_dotenv() | ~2015 onwards (adopted from Ruby Rails) | Standard Python practice; handles comments, multiline values; zero dependencies |
| Runtime provider detection (try each API in sequence) | Static provider config from .env at startup | 2024+ LLM tooling maturity | Prevents accidental cost spikes; clearer user intent; easier debugging |
| Hardcoded embedding model in ChromaDB | Metadata tracking + mismatch detection | This phase (Phase 6) | Prevents silent retrieval failures when embedding model changes |

**Deprecated/outdated:**
- Direct openai.OpenAI() instantiation in business logic: Use provider factory pattern instead. Harder to test; couples code to provider.
- Manual requests.post() to LLM APIs: Use LiteLLM or OpenAI client SDKs. Too error-prone (timeout handling, auth, retries).
- Env vars with inconsistent naming (OPENAI_KEY vs OPENAI_API_KEY): Standardize on {PROVIDER}_{CONFIG_TYPE} (e.g., OPENAI_API_KEY, OPENAI_MODEL).

## Open Questions

1. **Should we support custom LiteLLM Proxy as a provider?**
   - What we know: LiteLLM Proxy is an OpenAI-compatible server; can be treated as api_base target.
   - What's unclear: Is it in Phase 6 scope, or v2 future work?
   - Recommendation: Treat as future work (v2). Phase 6 handles direct LM Studio, cloud providers, Ollama. Proxy can be layered on top.

2. **Should streaming be configurable per-provider?**
   - What we know: All five target providers support streaming; LiteLLM handles it transparently.
   - What's unclear: Do we allow user to disable streaming (e.g., for low-latency UIs that want buffering)?
   - Recommendation: Out of Phase 6 scope. Streaming is default; disable via UI slider if needed (already exists in app.py).

3. **How to test provider switching in CI without real API keys?**
   - What we know: LiteLLM supports mock_response; pytest monkeypatch works; unittest.mock.patch recommended.
   - What's unclear: Do we mock all providers, or test with real LM Studio only in CI?
   - Recommendation: Mock all cloud providers (OpenAI, Anthropic, Gemini) in CI. Test LM Studio + Ollama with live servers in integration tests (optional, gated by CI env var).

4. **Should .env.example be generated automatically?**
   - What we know: .env.example is a template; user manually copies to .env and fills in values.
   - What's unclear: Should we write a script to generate .env.example from docstrings, or maintain it manually?
   - Recommendation: Manual .env.example is simpler. Include example for each provider (LM Studio with defaults, OpenAI with required keys, etc.).

5. **How to handle missing required keys gracefully (no crash)?**
   - What we know: get_llm_client() can raise ValueError if key is missing.
   - What's unclear: Should we fail fast (crash on startup), or lazy (fail on first API call)?
   - Recommendation: Lazy is better for UX. If .env missing, app starts with LM Studio fallback. If .env present but provider key missing, raise on first API call with helpful message.

## Environment Availability

**Skip condition:** This phase has no external tool dependencies beyond the Python environment and LM Studio (already running per project assumption). All libraries are pip-installable.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | LiteLLM, python-dotenv | ✓ (project requirement) | 3.10+ | — |
| pip | Dependency installation | ✓ | Latest | — |
| LM Studio | Default LLM/embedding provider | ✓ (project assumption) | Any with OpenAI-compat API | Use cloud provider via .env |
| OpenAI Python library | LiteLLM uses internally | ✓ (already in requirements.txt) | 1.0+ | — |
| httpx | OpenAI client HTTP transport | ✓ (already in requirements.txt) | 0.24+ | — |

**Missing dependencies with no fallback:** None. All packages are pip-installable and already in environment or requirements.txt.

**Missing dependencies with fallback:**
- OpenAI/Anthropic/Gemini API credentials: If user .env missing or keys unset, app falls back to hardcoded LM Studio. User can still use system without cloud providers.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ (already installed per requirements.txt) |
| Config file | pytest.ini (assumed to exist; tests run via `pytest tests/`) |
| Quick run command | `pytest tests/test_embed*.py -k "not e2e" -x --tb=short` |
| Full suite command | `pytest tests/ --cov=src/ --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROVIDER-01 | Load LLM provider from .env; fallback to LM Studio if absent | Unit | `pytest tests/test_config_providers.py::test_llm_client_from_env -x` | ❌ Wave 0 |
| PROVIDER-01 | Fallback to hardcoded LM Studio when .env missing | Unit | `pytest tests/test_config_providers.py::test_llm_client_fallback_without_env -x` | ❌ Wave 0 |
| PROVIDER-02 | LiteLLM routing works for LM Studio, Ollama, Gemini, OpenAI, Anthropic | Unit (mocked) | `pytest tests/test_config_providers.py -k "test_llm_provider" -x` | ❌ Wave 0 |
| PROVIDER-03 | Load embed provider from .env; fallback to LM Studio if absent | Unit | `pytest tests/test_config_providers.py::test_embed_client_from_env -x` | ❌ Wave 0 |
| PROVIDER-04 | LiteLLM embedding routing works for LM Studio, Ollama, Gemini, OpenAI | Unit (mocked) | `pytest tests/test_config_providers.py -k "test_embed_provider" -x` | ❌ Wave 0 |
| PROVIDER-05 | Changing .env LLM_PROVIDER/MODEL changes client without code change | Unit | `pytest tests/test_config_providers.py::test_llm_client_respects_env_changes -x` | ❌ Wave 0 |
| PROVIDER-06 | Embedding pipeline detects model mismatch; warns user; requires "yes" confirmation | Unit | `pytest tests/test_embed_pipeline.py::test_embed_model_mismatch_warning -x` | ❌ Wave 0 |
| PROVIDER-06 | Existing embedding tests pass with new factory pattern | Unit | `pytest tests/test_embedding.py -x` | ✅ Wave 0 (will need refactor to use get_embed_client) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_config_providers.py -x --tb=short` — All provider config tests must pass before merging any task.
- **Per wave merge:** `pytest tests/ --tb=short` — Full suite including existing embed/graph/query tests with refactored factory calls.
- **Phase gate:** Full suite green before `/gsd:verify-work` — All tests passing with new LiteLLM integration.

### Wave 0 Gaps

- [ ] `tests/test_config_providers.py` — Covers PROVIDER-01 through PROVIDER-05 (missing: all 5 tests)
- [ ] `tests/conftest.py` — Add fixtures: `mock_env_vars`, `mock_openai_client`, `mock_litellm_client` (update existing)
- [ ] `src/config/providers.py` — New module with get_llm_client(), get_embed_client(), validation logic
- [ ] `.env.example` — Template with all provider examples (LM Studio, Ollama, Gemini, OpenAI, Anthropic)
- [ ] Update existing tests in `test_embedding.py`, `test_graph_extraction.py`, `test_query_pipeline.py` to use get_embed_client() / get_llm_client() instead of hardcoded clients

*(Estimate: 8-10 tests to write in Wave 0; ~3-5 existing tests to refactor)*

## Sources

### Primary (HIGH confidence)

- [LiteLLM GitHub](https://github.com/BerriAI/litellm) - Confirmed 100+ provider support, openai/ prefix routing for OpenAI-compatible endpoints
- [LiteLLM Docs: OpenAI-Compatible Endpoints](https://docs.litellm.ai/docs/providers/openai_compatible) - api_base parameter, model prefix handling verified
- [LiteLLM Docs: Embeddings](https://docs.litellm.ai/docs/embedding/supported_embedding) - Embedding provider support, openai/ prefix for OAI-compatible servers
- [LiteLLM PyPI](https://pypi.org/project/litellm/) - Version 1.45+ confirmed current
- [python-dotenv GitHub](https://github.com/theskumar/python-dotenv) - Standard .env file loading, zero dependencies
- [python-dotenv PyPI](https://pypi.org/project/python-dotenv/) - Version 1.0+ confirmed current
- [LiteLLM Mock Requests](https://docs.litellm.ai/docs/completion/mock_requests) - Testing strategy with mock_response parameter

### Secondary (MEDIUM confidence)

- [LM Studio Docs: OpenAI Compatibility](https://lmstudio.ai/docs/developer/openai-compat) - Confirms LM Studio serves OpenAI-compatible API on localhost:1234/v1
- [Ollama LiteLLM Integration](https://apidog.com/blog/litellm-ollama/) - Example usage of LiteLLM with Ollama local models
- [Medium: Multi-Provider Chat App](https://medium.com/@richardhightower/multi-provider-chat-app-litellm-streamlit-ollama-gemini-claude-perplexity-and-modern-llm-afd5218c7eab) - Real-world integration patterns with Streamlit, LiteLLM, multiple providers

### Tertiary (LOW confidence — flagged for validation)

- Environment variable naming conventions inferred from community patterns (DeepEval, Aider, AnythingLLM) — no official Python standard document exists; recommendation based on industry consensus.
- Specific LiteLLM version stability in 2026 — assumed based on Feb 2025 knowledge; recommend pip list output before Phase 6 execution.

## Metadata

**Confidence breakdown:**
- **Standard stack (LiteLLM + python-dotenv):** HIGH — Both widely adopted, stable APIs documented
- **Provider routing (openai/ prefix, api_base):** HIGH — LiteLLM docs and LM Studio docs both confirm pattern
- **Architecture patterns (factory functions, .env loading):** HIGH — Verified against official examples
- **Testing strategy (mock_response, pytest monkeypatch):** MEDIUM — LiteLLM mocking works; specific integration tests to be written in Wave 0
- **Environment variable naming conventions:** MEDIUM — Based on community patterns (DeepEval, Aider); no single Python standard exists

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (LiteLLM and python-dotenv are stable; 30-day review recommended for version updates)

**Next steps for planner:**
1. Create src/config/providers.py with get_llm_client() and get_embed_client() factories
2. Create .env.example with template variables for all 5 providers
3. Update app.py, embed/pipeline.py, graph/pipeline.py, query/pipeline.py to call get_llm_client() / get_embed_client()
4. Add embedding model tracking to SQLite metadata table and mismatch detection in embed_all_chunks()
5. Write tests for provider config, .env loading, mismatch detection, fallback behavior
6. Update all existing tests to work with new factory pattern (mock or pass get_*_client() result)
