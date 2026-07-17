# Codebase design for AI agents — deep modules

Type: principle
Status: resolved (standing discipline for the build)
Relates to: 05 (MemoryEngine facade), 07 (extraction pipeline), 08 (MVP scope)

## Why

Every agent that touches this repo — and future-me — arrives with **no memory**, a new starter
each time (the guy from Memento: "okay, I'm here, what am I doing?"). The codebase, far more than
any prompt or `AGENTS.md`, decides whether that new starter does good work or flails. A web of
small modules that all import each other is unnavigable, untestable, and forces the whole thing to
be held in one head. **Design the file system to match the mental map.** What's been good practice
for humans for 20 years is exactly what an AI new-starter needs.

## The discipline: deep modules with grey-box boundaries

(from *A Philosophy of Software Design* + the `/codebase-design` skill the map already consults)

- **Deep modules** — lots of implementation behind a small, deliberately-designed interface. A few
  big chunks (~7–8), not dozens of shallow ones. Every export goes *through* the interface.
- **Grey-box split** — I own and design the **interface**; the **implementation** inside can be
  delegated to an agent; **tests** lock the behavior so no one has to read the insides to trust
  them. As long as the tests pass, the box stays closed. Open it only to apply taste or perf.
- **Navigability / progressive disclosure** — each module is a folder with a clear public surface
  at the top (types + docstrings that say *what it does*); you open the implementation only when
  you must.
- **Tests are the feedback loop** — they're how an agent knows a change to a closed box actually
  did what it intended. No boundary ships without them.

## The modules for mirror (the ~7 chunks)

- **MemoryEngine** (ticket 05) — THE facade. `ingest(entry)`, `ask(question)`, the analytical
  primitives. The app talks only to this. Deepest box: hides Graphiti/FalkorDB entirely; it's the
  one seam we'd re-implement behind if we ever left Graphiti.
- **EntryStore** — the **source of truth**: proofread `{date, text}` entries, content-addressed for
  **exact** identity (ticket 08). The graph is *derived from this and rebuildable*. Interface:
  put / get / list / hash; an edit triggers re-derive-forward.
- **extraction** — the prototype hardened: ontology + providers + ensemble + edge-dedup. Interface:
  "entry in → typed facts in the graph". Ontology docstrings + custom instructions live here, not
  scattered.
- **Transcriber** (ticket 04) — audio/photo → text. One swappable seam.
- **Normalizer** (ticket 05) — the *only* format-aware code: photo / typed / audio → a uniform
  `{date, text}` episode. All source-format knowledge in one place.
- **providers** — LLM / embedder / reranker chosen by `.env` (already built, ticket 05).
- **web** — FastAPI backend + browser UI. Talks **only** to MemoryEngine.

## Rules for this repo

1. The app never imports Graphiti / FalkorDB directly — only **MemoryEngine**.
2. Each module owns a folder + a public entry point (`__init__` or one clear module file) that
   states its interface; implementation details don't leak across boundaries.
3. Every boundary gets **behavior-locking tests** before its box is closed.
4. **Source of truth (EntryStore) is sacred and separate from derived state (the graph); derived
   state is always rebuildable from the source.** This is a module boundary, not just a data rule —
   it's what makes re-derive-forward (ticket 08) safe and testable.
5. Prefer a few deep modules to many shallow ones. If a new file only forwards calls, it's shallow —
   fold it in.

## Not this

- **Not** a framework or speculative abstraction layer — ticket 05 already rejected a parallel
  abstraction over Graphiti. Deep modules ≠ more layers; they mean *fewer, better-sealed* ones.
- **Not** big-bang. Applied as the MVP is built, module by module, tests first at each seam.
