# Provider adapter boundary design

Type: grilling
Status: open
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
