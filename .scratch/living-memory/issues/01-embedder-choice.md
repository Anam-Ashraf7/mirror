# Embedder: Gemini embeddings or a local model?

Type: grilling
Status: resolved
Blocked by: —

## Question

Extraction is locked to Gemini 2.5 Pro. Graphiti also needs an **embedder** (for semantic
retrieval / RAG fallback), and that role *can* be small or local without much quality loss.

Decide the embedder:
- **Gemini embeddings** — one vendor, one key, simplest; data already goes to Google for
  extraction so no new exposure surface (recommended default).
- **Local open embedder** (BGE / sentence-transformers) — keeps the *bulk* of repeated
  processing on-machine; a step toward eventual full-local extraction.

Either way it sits behind the provider adapter (see *Provider adapter boundary*). Resolve which
is the day-one default and why.

## Answer

**Gemini embeddings.** Extraction already sends entries to Google, so a local embedder buys no
privacy today — it only adds a second moving part to keep consistent across laptop and prod. Keep
one provider end-to-end. Still behind the provider adapter, so a local embedder gets revisited as
part of the *same* future move that takes extraction local.
