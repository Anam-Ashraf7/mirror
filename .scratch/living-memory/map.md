# Map: Living Memory of a Person

Label: `wayfinder:map`

## Destination

A **build-ready implementation spec for the single-user core engine** of the living-memory
system — every architectural decision locked so a builder can start with no open questions.

"Living memory" = a **temporal knowledge graph of the self**, built from journal entries
(handwritten → photo, typed, or audio), that answers longitudinal questions — *"how have I
changed in 3 years?"*, *"what did I struggle with most, and how is it now?"*, *"what patterns
do I miss?"* — with answers **grounded in what was actually written**, not plausible narrative.

## Notes

**Domain:** personal reflective journaling (3 yrs of meditation practice); temporal knowledge
graphs; retrieval-augmented generation. The user is the sole first user and owns the corpus.

**Skills every session should consult:** `/grilling`, `/domain-modeling`, `/research`,
`/prototype`, `/codebase-design`.

**Plan, don't do** — with one carve-out: the *Extraction-quality prototype* ticket produces a
rough concrete artifact to react to, and actual build of the engine graduates as a *follow-on
effort* once this spec is locked. No production build during this map.

**Locked constraints (settled during the charting grill — these shape every ticket):**

- **Scope:** single-user personal tool first; clean **adapter boundaries** so DB / graph / LLM /
  storage swap from local to production-grade later. Multi-user deferred.
- **Substrate:** **Graphiti** (temporal knowledge graph), self-hosted. Bi-temporal fact model
  (valid-time + transaction-time) is the reason — it powers "then vs now".
- **Graph backend:** **FalkorDB** — one backend from laptop to prod (single Docker container),
  no swap needed. (Kuzu is deprecated in Graphiti; Neo4j rejected as heavier.)
- **Runtime:** Python (Graphiti is a Python library).
- **Extraction LLM:** **Gemini 2.5 Pro** — also multimodal, so it doubles as the handwriting
  OCR + date reader for notebook photos.
- **Representation:** hybrid — a curated **typed person-ontology** + Graphiti's **open-ended**
  extraction running alongside + raw entries embedded for RAG fallback.
- **Person ontology (approved):** anchored on a single **Subject** node.
  - Entities: `Struggle`, `Practice`, `EmotionalState`, `Insight`, `Relationship`, `Intention`.
  - Edges: `STRUGGLES_WITH`, `PRACTICES`, `EXPERIENCES`, `REALIZED`, `TRIGGERED_BY`,
    `ADDRESSES`, `SHIFTED_TO`. Coarse buckets (e.g. intensity subtle/moderate/strong) chosen
    for cross-year consistency over false precision.
- **Ingestion:** one journal entry = one Graphiti **episode**, stamped with its **authored date**
  as `reference_time`, ingested **oldest-first**. No bulk backfill required — incremental,
  test-a-few-then-add-going-forward.
- **Sources:** handwritten notebooks (photo → Gemini vision transcribe + date extract), plus
  going-forward direct **text** or **audio** entry.
- **Proofread gate (non-negotiable):** every source (photo transcript + detected date, audio
  transcript) is proofread and confirmed by the user *before* it enters the graph. Trust in the
  data is the whole product.
- **Query discipline:** deterministic **analytical primitives** (Timeline / Transitions /
  Ranking / CoOccurrence) for quantitative claims **+** raw graph access for open exploration;
  **every answer cites the source entries**. LLM narrates, never invents facts.
- **Observed vs Inferred split (baked in day one):** what you wrote (proofread, sacred) lives
  apart from machine-hypothesized connections (provenance-tagged, surfaced for confirmation).

## Decisions so far

<!-- index — one line per resolved ticket; fills as the map is worked -->

- [Reflection engine: day-one or phase-two?](issues/02-reflection-engine-timing.md) — **phase-two**; Observed/Inferred split built day-one, proactive engine waits until the graph has history to mine.
- [Embedder: Gemini or local?](issues/01-embedder-choice.md) — **Gemini embeddings**; one provider end-to-end, local embedder deferred to the future local-extraction move.
- [Interaction surface](issues/03-interaction-surface.md) — **local web app** on localhost (Python backend + browser frontend); the visual proofread gate + cited answers need a UI, and it's the seed of the future multi-user product. Chat lives inside it.
- [Audio transcription approach](issues/04-audio-transcription.md) — **faster-whisper local** behind a `Transcriber` adapter; raw voice never leaves the machine, $0/min, offline, proofread gate covers accuracy. Fallback: Gemini audio → hosted STT.
- [Entity resolution & consistency](issues/06-entity-resolution-consistency.md) — **handled natively** (auto node-dedup via `SAME_AS` components + bi-temporal contradiction invalidation); Gemini + `json_schema` + atomic attributes as mitigations. Three drift risks handed to the prototype (07).
- [Provider adapter boundary](issues/05-provider-adapter-boundary.md) — **lean on Graphiti's provider system; wrap only the gaps**: build `Transcriber` + `Normalizer` + a `MemoryEngine` facade (the app's one entry point); config via `.env` + a providers config. No parallel abstraction over Graphiti.
- [Longitudinal answer & citation UX](issues/09-longitudinal-answer-ux.md) — **three-layer, narrative-first** (narrative → transition timeline → cited source entries); no claim shown without a citation; graceful refusal + suggested answerable questions. [Mockup published.](https://claude.ai/code/artifact/9f745aa5-4e02-473b-a072-ff8c8e01c3d1)

## Not yet specified

<!-- in-scope fog; graduates into tickets as the frontier advances -->

- **Reflection-engine mechanics** — how the background pass proposes new edges into the Inferred
  layer, and the confirm-to-promote UX. Sharpens once *Reflection-engine timing* is decided.
- **Cost & rate-limit handling** for Gemini during transcription + extraction at entry volume.
- **Journal-store privacy** — encryption-at-rest of raw entries; matters more as multi-user nears.
- **Prod-hardening / multi-user migration path** — hinges on the adapter-boundary design and the
  chosen interaction surface.

## Out of scope

<!-- ruled beyond this map's destination; returns only if the destination is redrawn -->

- **Precomputed "state-of-you" rollup nodes** — a real optimization for instant "then vs now",
  but explicitly a phase-two concern; not part of the core-engine MVP spec.
- **Multi-user product** (auth, accounts, moderation, consent flows) — architected-*for* via
  adapters, not built in this effort.
