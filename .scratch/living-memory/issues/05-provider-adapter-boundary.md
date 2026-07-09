# Provider adapter boundary design

Type: grilling
Status: resolved
Blocked by: 01, 04

## Question

The "local now, production-grade later, easily switchable" promise lives or dies on clean
boundaries. Design the adapter seams so LLM, embedder, transcription, and graph backend are each
swappable by config with zero rearchitecting.

Pin down:
- The interface(s): `ExtractionLLM`, `Embedder`, `Transcriber`, `GraphStore` — methods, shapes.
- Which concerns are format-aware and confined to the **normalizer** (the only piece that knows
  about notebooks vs typed vs audio), producing a uniform `{date, text}` episode.
- Config/wiring approach (env + a providers config), and how the eventual local-extraction and
  multi-user swaps stay one-config-flip changes.

Depends on the embedder (01) and transcription (04) choices being known.

## Answer

**Lean on Graphiti's built-in provider system; wrap only the gaps.** Graphiti already ships
pluggable `LLMClient` / `EmbedderClient` / `GraphDriver` interfaces and an OpenAI-compatible client
(for a future local Ollama/vLLM extraction swap), and we chose FalkorDB for *both* local and prod —
so the LLM/embedder/backend swappability we need is already covered by config. Building a parallel
abstraction over that is speculative insulation; skip it.

**What we build (only what Graphiti doesn't own):**
- `Transcriber` — `transcribe(audio) -> text`; impl = local faster-whisper (per ticket 04). The one
  seam for swapping to Gemini-audio / hosted STT.
- `Normalizer` — the *only* format-aware code: notebook-photo / typed / audio → a uniform
  `{date, text}` episode. Keeps all source-format knowledge in one place.
- `MemoryEngine` facade — the single object the web app calls (`ingest(entry)`, `ask(question)`,
  the analytical primitives). The app never touches Graphiti directly; this facade *is* the one
  seam we'd re-implement behind if we ever left Graphiti — exactly enough insulation, no more.

**Config/wiring:** secrets in git-ignored `.env` (Gemini key); a `providers` config selecting
LLM/embedder/backend + Transcriber impl, so local↔prod and cloud↔local-extraction are one-config
changes. Graphiti gets configured from that at startup.
