"""Provider factory — pick the LLM / embedder / reranker trio by `MIRROR_LLM_PROVIDER`.

The whole pipeline switches between Google, OpenAI, or ANY OpenAI-compatible endpoint
(DeepSeek / OpenRouter / Ollama / LiteLLM, via `openai_generic` + a base_url) with a single
`.env` change — no code edit. This leans on Graphiti's own pluggable client system rather than
bolting on a separate multi-provider SDK, which is the ticket-05 decision: "lean on Graphiti's
provider system; wrap only the gaps."

Every model id + key is read from `.env`, so trying a new model or provider never touches code.
"""

from __future__ import annotations

import os

from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.client import LLMClient
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.cross_encoder.client import CrossEncoderClient

# Per-provider defaults. `keys` lists the .env variable names accepted for that provider's API
# key, in priority order (first found wins) — so both OPENAI_API_KEY and the OPEN_AI_API_KEY
# spelling work. Everything here is overridable from .env.
_PROVIDERS: dict[str, dict] = {
    "gemini": {
        "keys": ["GEMINI_API_KEY"],
        "chain": "gemini-3-flash-preview,gemini-3.1-flash-lite",
        "small": "gemini-3.1-flash-lite",
        "embed": "gemini-embedding-001",
        "rerank": "gemini-3.1-flash-lite",
    },
    "openai": {
        "keys": ["OPENAI_API_KEY", "OPEN_AI_API_KEY"],
        "chain": "gpt-5.4-nano",           # cheapest current-gen; trying nano first
        "small": "gpt-5.4-nano",
        "embed": "text-embedding-3-small",
        "rerank": "gpt-5.4-nano",
    },
    # Anyone OpenAI-compatible: set MIRROR_LLM_BASE_URL + MIRROR_LLM_MODEL (+ its key).
    "openai_generic": {
        "keys": ["OPENAI_API_KEY", "OPEN_AI_API_KEY", "MIRROR_LLM_API_KEY"],
        "chain": "",
        "small": "",
        "embed": "text-embedding-3-small",
        "rerank": "",
    },
}


# Primary-sourced list prices, USD per 1M tokens (input, output). Embeddings omitted — a
# rounding error at our scale, and the token tracker only counts chat/LLM calls anyway.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.4": (2.50, 15.00),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float | None:
    p = PRICES.get(model)
    return None if p is None else input_tokens / 1e6 * p[0] + output_tokens / 1e6 * p[1]


def provider_name() -> str:
    return os.getenv("MIRROR_LLM_PROVIDER", "gemini").strip().lower()


def _cfg(provider: str) -> dict:
    if provider not in _PROVIDERS:
        raise SystemExit(
            f"  Unknown MIRROR_LLM_PROVIDER={provider!r}. "
            f"Use one of: {', '.join(_PROVIDERS)}."
        )
    return _PROVIDERS[provider]


def api_key(provider: str | None = None) -> str:
    provider = provider or provider_name()
    names = _cfg(provider)["keys"]
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    raise SystemExit(f"  Set {names[0]} in .env (provider={provider}).")


def _base_url() -> str | None:
    return os.getenv("MIRROR_LLM_BASE_URL") or None


def model_chain(provider: str | None = None) -> list[str]:
    """Extraction models to try in order — the ingest loop drops to the next on a transient
    503/overload. One id is fine; a comma-separated list gives fallback headroom."""
    provider = provider or provider_name()
    raw = os.getenv("MIRROR_LLM_MODEL", _cfg(provider)["chain"])
    chain = [m.strip() for m in raw.split(",") if m.strip()]
    if not chain:
        raise SystemExit(f"  No model set — provide MIRROR_LLM_MODEL for provider={provider}.")
    return chain


def small_model(provider: str | None = None) -> str:
    """Graphiti's cheaper model for attribute extraction / dedup."""
    provider = provider or provider_name()
    return os.getenv("MIRROR_SMALL_MODEL", _cfg(provider)["small"])


def embed_model(provider: str | None = None) -> str:
    provider = provider or provider_name()
    return os.getenv("MIRROR_EMBED_MODEL", _cfg(provider)["embed"])


def rerank_model(provider: str | None = None) -> str:
    provider = provider or provider_name()
    return os.getenv("MIRROR_RERANK_MODEL", _cfg(provider)["rerank"])


def make_llm_client(model: str, provider: str | None = None) -> LLMClient:
    provider = provider or provider_name()
    cfg = LLMConfig(
        api_key=api_key(provider),
        model=model,
        small_model=small_model(provider),
        base_url=_base_url(),
    )
    if provider == "gemini":
        from graphiti_core.llm_client.gemini_client import GeminiClient
        return GeminiClient(config=cfg)
    if provider == "openai":
        from graphiti_core.llm_client.openai_client import OpenAIClient
        # GPT-5 reasoning models reject Graphiti's default effort='minimal'; the nano tier
        # accepts none/low/medium/high/xhigh. 'low' balances extraction nuance vs cost.
        reasoning = os.getenv("MIRROR_OPENAI_REASONING", "low")
        return OpenAIClient(config=cfg, reasoning=reasoning)
    if provider == "openai_generic":
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
        return OpenAIGenericClient(config=cfg)
    raise SystemExit(f"  Unknown provider {provider!r}")


def make_embedder(provider: str | None = None) -> EmbedderClient:
    provider = provider or provider_name()
    key, model = api_key(provider), embed_model(provider)
    if provider == "gemini":
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
        return GeminiEmbedder(config=GeminiEmbedderConfig(api_key=key, embedding_model=model))
    # openai + openai_generic share the OpenAI embedder (honors base_url)
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(api_key=key, embedding_model=model, base_url=_base_url())
    )


def make_reranker(provider: str | None = None) -> CrossEncoderClient:
    """Only used at SEARCH time, not during ingest — but wire it correctly per provider."""
    provider = provider or provider_name()
    cfg = LLMConfig(api_key=api_key(provider), model=rerank_model(provider), base_url=_base_url())
    if provider == "gemini":
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
        return GeminiRerankerClient(config=cfg)
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    return OpenAIRerankerClient(config=cfg)
