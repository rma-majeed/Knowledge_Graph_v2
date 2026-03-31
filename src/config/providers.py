"""Provider factory functions for LLM and embedding clients.

Reads configuration from environment variables (loaded from .env via python-dotenv).
Defaults to LM Studio at localhost:1234 when no .env file exists or provider is unset.

Supported LLM providers: lm-studio (default), ollama, gemini, openai, anthropic
Supported embed providers: lm-studio (default), ollama, gemini, openai

Usage:
    from src.config.providers import get_llm_client, get_embed_client

    llm = get_llm_client()    # OpenAI-compatible client or LiteLLM config
    emb = get_embed_client()  # OpenAI-compatible client or LiteLLM config
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _load_dotenv() -> None:
    """Load .env file from project root if present. No-op if file does not exist."""
    try:
        from dotenv import load_dotenv
        dotenv_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(dotenv_path=str(dotenv_path), override=False)
    except ImportError:
        pass  # python-dotenv not installed — rely on environment variables only


# Load .env once at module import time
_load_dotenv()


def load_provider_config() -> dict[str, str]:
    """Read all provider config from environment variables.

    Returns a typed dict with keys:
        llm_provider, llm_model, llm_api_key, llm_api_base
        embed_provider, embed_model, embed_api_key, embed_api_base

    Defaults:
        llm_provider  = "lm-studio"
        llm_model     = "Qwen2.5-7B-Instruct"
        embed_provider = "lm-studio"
        embed_model   = "nomic-embed-text-v1.5"
    """
    llm_provider = os.getenv("LLM_PROVIDER", "lm-studio").lower().strip()
    embed_provider = os.getenv("EMBED_PROVIDER", "lm-studio").lower().strip()

    return {
        "llm_provider": llm_provider,
        "llm_model": os.getenv("LLM_MODEL", "Qwen2.5-7B-Instruct"),
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "llm_api_base": os.getenv("LLM_API_BASE", ""),
        "embed_provider": embed_provider,
        "embed_model": os.getenv("EMBED_MODEL", "nomic-embed-text-v1.5"),
        "embed_api_key": os.getenv("EMBED_API_KEY", ""),
        "embed_api_base": os.getenv("EMBED_API_BASE", ""),
    }


def get_llm_client() -> Any:
    """Return configured LLM client based on LLM_PROVIDER environment variable.

    LM Studio (default, when LLM_PROVIDER unset or 'lm-studio'):
        Returns raw openai.OpenAI client pointing to http://localhost:1234/v1
        Backward compatible — identical to existing hardcoded client.

    Other providers (openai, ollama, gemini, anthropic):
        Returns a _LiteLLMConfig namedtuple with (model, api_key, api_base) fields.
        Callers use litellm.completion(**client._asdict(), messages=[...]) pattern.

    Raises:
        ValueError: If provider requires API key but LLM_API_KEY is unset.
        ImportError: If litellm not installed and a non-lm-studio provider is requested.
    """
    config = load_provider_config()
    provider = config["llm_provider"]

    if provider in ("lm-studio", "lmstudio", ""):
        from openai import OpenAI
        api_base = config["llm_api_base"].rstrip("/v1").rstrip("/") or "http://localhost:1234"
        return OpenAI(base_url=f"{api_base}/v1", api_key="lm-studio")

    import litellm  # noqa: F401 — validates installation

    api_key = config["llm_api_key"]
    model_name = config["llm_model"]
    api_base = config["llm_api_base"]

    # Validate required keys for cloud providers
    _KEYLESS_PROVIDERS = {"ollama"}
    if provider not in _KEYLESS_PROVIDERS and not api_key:
        raise ValueError(
            f"LLM_API_KEY must be set in .env when LLM_PROVIDER={provider!r}. "
            f"Get your key from the {provider} dashboard and add it to .env."
        )

    if not model_name:
        raise ValueError(
            f"LLM_MODEL must be set in .env when LLM_PROVIDER={provider!r}."
        )

    # Build LiteLLM call kwargs as a simple namespace object
    # Callers use: litellm.completion(**get_llm_client(), messages=[...])
    return _LiteLLMConfig(
        provider=provider,
        model=_build_litellm_model(provider, model_name),
        api_key=api_key or "ollama",
        api_base=_build_litellm_api_base(provider, api_base),
    )


def get_embed_client() -> Any:
    """Return configured embedding client based on EMBED_PROVIDER environment variable.

    LM Studio (default, when EMBED_PROVIDER unset or 'lm-studio'):
        Returns raw openai.OpenAI client pointing to http://localhost:1234/v1
        Backward compatible — identical to existing hardcoded client.

    Other providers (openai, ollama, gemini):
        Returns a _LiteLLMConfig with model/api_key/api_base for litellm.embedding() calls.

    Raises:
        ValueError: If provider requires API key but EMBED_API_KEY is unset.
    """
    config = load_provider_config()
    provider = config["embed_provider"]

    if provider in ("lm-studio", "lmstudio", ""):
        from openai import OpenAI
        api_base = config["embed_api_base"].rstrip("/v1").rstrip("/") or "http://localhost:1234"
        return OpenAI(base_url=f"{api_base}/v1", api_key="lm-studio")

    import litellm  # noqa: F401 — validates installation

    api_key = config["embed_api_key"]
    model_name = config["embed_model"]
    api_base = config["embed_api_base"]

    _KEYLESS_PROVIDERS = {"ollama"}
    if provider not in _KEYLESS_PROVIDERS and not api_key:
        raise ValueError(
            f"EMBED_API_KEY must be set in .env when EMBED_PROVIDER={provider!r}."
        )

    if not model_name:
        raise ValueError(
            f"EMBED_MODEL must be set in .env when EMBED_PROVIDER={provider!r}."
        )

    return _LiteLLMConfig(
        provider=provider,
        model=_build_litellm_model(provider, model_name),
        api_key=api_key or "ollama",
        api_base=_build_litellm_api_base(provider, api_base),
    )


def get_current_embed_provider() -> str:
    """Return current EMBED_PROVIDER value (lowercase). Defaults to 'lm-studio'."""
    return os.getenv("EMBED_PROVIDER", "lm-studio").lower().strip()


def get_current_embed_model() -> str:
    """Return current EMBED_MODEL value. Defaults to 'nomic-embed-text-v1.5'."""
    return os.getenv("EMBED_MODEL", "nomic-embed-text-v1.5").strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _LiteLLMConfig:
    """Lightweight config container returned by get_llm_client/get_embed_client for non-LM Studio providers.

    Usage in pipeline code:
        client = get_llm_client()
        if hasattr(client, 'provider'):  # is _LiteLLMConfig
            import litellm
            response = litellm.completion(model=client.model, api_key=client.api_key,
                                          api_base=client.api_base, messages=[...])
        else:  # raw OpenAI client
            response = client.chat.completions.create(model=..., messages=[...])
    """

    def __init__(self, provider: str, model: str, api_key: str, api_base: str | None):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.api_base = api_base

    def __repr__(self) -> str:
        return f"_LiteLLMConfig(provider={self.provider!r}, model={self.model!r})"


def _build_litellm_model(provider: str, model_name: str) -> str:
    """Build the LiteLLM model string for a given provider and model name.

    LiteLLM routing conventions:
      - openai:    openai/gpt-4o  (already has openai/ prefix -> use as-is)
      - ollama:    openai/llama2  (routed via Ollama's OpenAI-compat endpoint)
      - gemini:    gemini/gemini-2.5-flash
      - anthropic: anthropic/claude-sonnet-4-5
    """
    # If model already has a provider/ prefix, use it unchanged
    if "/" in model_name:
        return model_name

    prefix_map = {
        "openai": "openai",
        "ollama": "openai",    # Ollama exposes OpenAI-compatible endpoint
        "gemini": "gemini",
        "anthropic": "anthropic",
    }
    prefix = prefix_map.get(provider, provider)
    return f"{prefix}/{model_name}"


def _build_litellm_api_base(provider: str, api_base: str) -> str | None:
    """Return the api_base URL for LiteLLM, or None to use provider default.

    Strips trailing /v1 to avoid double-path (LiteLLM appends /v1 internally
    for openai-compatible endpoints).
    """
    if api_base:
        return api_base.rstrip("/v1").rstrip("/")

    # Provider-specific defaults
    defaults: dict[str, str | None] = {
        "ollama": "http://localhost:11434",
        "openai": None,     # LiteLLM uses OpenAI default
        "gemini": None,     # LiteLLM uses Gemini default
        "anthropic": None,  # LiteLLM uses Anthropic default
    }
    return defaults.get(provider)
