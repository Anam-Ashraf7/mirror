# Findings: LLM API providers — free tiers, pay-as-you-go, and switching

Research asset for ticket [05-provider-adapter-boundary](../issues/05-provider-adapter-boundary.md).
Prompted by "which provider is best + estimated cost of everything, and can an SDK let us switch
easily?" — after the Gemini free tier proved unable to sustain iterative dev (503s on the newest
model, 429 rate limits after ~8 runs; see ticket 07 findings).

## The core problem this note answers

mirror needs, per run over a few years of entries: **extraction LLM** (the expensive part —
structured output over every episode), a **small model** (attribute extraction / dedup), an
**embedder**, and a **reranker**. At this scale the whole thing is pennies on pay-as-you-go — the
blocker was never cost, it was **free-tier rate limits killing the dev loop**.

## Privacy filter (applied first, because this is a diary)

This is personal meditation-journal data, so any provider that trains on inputs or shares data is
disqualified for real use, regardless of price:

- **Grok (xAI)** — free tier is explicitly **data-sharing** (inputs used for training). ❌ for diary.
- **Chinese first-party endpoints** (DeepSeek/Qwen `.cn`) — data residency + training-use concerns
  for a diary. The *international* endpoints (e.g. Qwen via Alibaba Singapore, DeepSeek's paid API)
  have clearer terms but still read them.
- **Gemini paid / OpenAI paid / Anthropic paid** — paid tiers do **not** train on API data. ✅
- **Local (Ollama)** — nothing leaves the machine. ✅✅ strongest privacy; no rate limits ever.

## Provider comparison

| Provider / model | Free tier | Pay-as-you-go (text) | Diary-safe? | Notes |
|---|---|---|---|---|
| **Gemini** 3.x Flash / Flash-Lite | yes, but 503s on newest + ~8-run 429 wall | ~$0.10–0.40 / 1M in, cheap | ✅ paid | Already integrated (`GeminiClient` + embedder + reranker). ~$25 one-time / ~$1–2/mo for this project. |
| **DeepSeek** V3 (intl paid API) | limited | **cheapest capable text model** | ⚠️ read terms | Great price/quality; via `OpenAIGenericClient` + base_url. |
| **GLM-4.7-Flash** (Zhipu) | **free, no hard limits** | n/a | ⚠️ read terms | Genuinely free + usable for dev iteration; verify data policy before real entries. |
| **Qwen** (Alibaba intl) | modest | cheap | ⚠️ intl endpoint | Strong models; Singapore endpoint for residency. |
| **OpenAI** GPT (mini tier) | none | low-mid | ✅ paid | Native `OpenAIClient` **ignores base_url** — use `OpenAIGenericClient` for compatible endpoints. |
| **Anthropic** Claude Haiku | none | low-mid | ✅ paid | Excellent extraction quality; no first-party Graphiti embedder. |
| **OpenRouter** (aggregator) | varies | routes to any of the above | depends on route | One key, many models; good for A/B-ing providers via one base_url. |
| **Ollama** (local) | **∞ free, private** | $0 | ✅✅ | No rate limits; quality ceiling = your hardware. rowboat-style fully-local path. |

## Switching providers easily — the SDK question

**We already have the seam; we don't need a new SDK.** Graphiti ships pluggable `LLMClient` /
`EmbedderClient`, and its **`OpenAIGenericClient` honors `base_url`** — so DeepSeek, OpenRouter,
Qwen-intl, LiteLLM, and Ollama are all reachable as OpenAI-compatible endpoints by config alone.
The native `OpenAIClient` does **not** honor base_url — must use the *Generic* one.

Planned tiny addition (not a new abstraction — just wiring): a `MIRROR_LLM_PROVIDER` switch that
selects `GeminiClient` vs `OpenAIGenericClient(base_url=…)`, so provider is a one-`.env`-flip change.
`LiteLLM` (or OpenRouter) is the fallback if we ever want a single proxy over *all* of them, but
that's speculative until we actually juggle 3+ providers.

## Recommendation

1. **Dev loop:** go **fully local with Ollama** (private, zero rate limits, rowboat-inspired) *or*
   use **GLM-4.7-Flash free** for cheap iteration — either unblocks the "8 runs and you're walled"
   problem that stalled ticket 07.
2. **Quality runs / real entries:** **Gemini paid** (already wired, embedder+reranker native,
   ~$1–2/mo) — or **DeepSeek paid** if we want cheapest capable extraction via the generic client.
3. **Never** feed real entries to Grok-free or unclear-policy first-party CN endpoints.
4. Keep the provider switch as one env var behind the `OpenAIGenericClient` base_url seam we
   already have — no new SDK required.

## Sources
- [Graphiti LLM configuration / clients | Zep docs](https://help.getzep.com/graphiti/configuration/llm-configuration)
- [OpenAI-compatible providers (base_url) | Graphiti](https://help.getzep.com/graphiti/configuration/llm-configuration)
- Provider pricing/policy pages (Gemini, DeepSeek, Zhipu GLM, Qwen, xAI, OpenAI, Anthropic, OpenRouter) — verify current terms before committing real data.
