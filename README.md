# mirror

*A living memory of a person* — a temporal knowledge graph of the self, built from
journal entries (handwritten → photo, typed, or spoken), that answers **longitudinal**
questions grounded in what you actually wrote:

- *How much have I changed in three years?*
- *What did I struggle with most — and how is it now?*
- *What patterns am I too close to see?*

The full design lives as a **wayfinder map** in [`.scratch/living-memory/`](.scratch/living-memory/map.md).

## Locked architecture

| Concern | Decision |
|---|---|
| Memory substrate | **Graphiti** — temporal knowledge graph (bi-temporal facts power "then vs now") |
| Graph backend | **FalkorDB** — one container, laptop → prod, no swap |
| Extraction & vision | **Provider-switchable** via `.env` (`MIRROR_LLM_PROVIDER=gemini\|openai\|openai_generic`) — Gemini Flash reads handwriting *and* extracts; currently defaulting to OpenAI `gpt-5.4-nano` for iteration. One flip, no code change. |
| Embeddings | matches the provider (Gemini or OpenAI), single vendor per run |
| Representation | typed **person-ontology** + Graphiti's open-ended extraction, side by side |
| Audio (going-forward) | **local faster-whisper** — raw voice never leaves the machine |
| Interface | **local web app** — visual proofread gate + cited answers |
| Trust rules | proofread gate before ingest · deterministic query primitives · **every answer cites source entries** · Observed vs Inferred layers |

Answer-view design: see the [mockup](https://claude.ai/code/artifact/9f745aa5-4e02-473b-a072-ff8c8e01c3d1).

## Prototype (Stage 1) — is the extraction any good?

This proves the crown jewel on *real* entries before building anything else.

```bash
docker compose up -d              # start FalkorDB (graph UI at http://localhost:3000)
cp .env.example .env              # then put your GEMINI_API_KEY in .env
pip install -r requirements.txt

# put page images in data/entries/, named by date (with -N for multi-page entries):
#   data/entries/2024-01-06-1.jpeg   ┐
#   data/entries/2024-01-06-2.jpeg   ├─ one 4-page entry, dated 2024-01-06
#   data/entries/2024-01-06-3.jpeg   │
#   data/entries/2024-01-06-4.jpeg   ┘
#   data/entries/2025-01-03.jpeg      ── one single-page entry

python -m mirror.transcribe       # 1. images -> data/transcripts/*.md  (Gemini vision)
                                  #    ...then PROOFREAD the transcripts (the trust gate)
python -m mirror.prototype        # 2. ingest oldest-first, then print the graph
```

Pages of one entry (same date) are merged into a **single** episode, stamped with that
date. `data/` is git-ignored — your journals and transcripts stay local.

## MVP — the app (Stage 2)

The walking skeleton is built: a local web app that answers longitudinal questions grounded in
your entries. It's organized as a few **deep modules** behind a single `MemoryEngine` facade —
the app never touches Graphiti directly.

```bash
docker compose up -d              # FalkorDB
# .env already set (provider + key)
pip install -r requirements.txt
uvicorn mirror.web.app:app        # open http://127.0.0.1:8000
#   → click "Sync graph from entries", then ask
#     e.g. "What did I struggle with most, and where is it now?"
```

| Module | Role |
|---|---|
| `entry_store.py` | **source of truth** — proofread `{date,text}`, exact date-identity + hash-version |
| `extraction.py` | derives the graph — **no-wipe, incremental, re-derive-forward** on edits |
| `theme_resolver.py` | unifies a scattered theme (anger-the-feeling + holding-anger-the-struggle) |
| `primitives.py` | Ranking + Transitions → a **grounded, cited** answer |
| `engine.py` | `MemoryEngine` facade — `ingest()` / `ask()` |
| `web/` | FastAPI + one browser page (narrative → per-year → grouped themes → citations → correct-me) |

Every answer cites the source entries; the graph is a **derived cache** rebuilt from the entries,
which are sacred. Run the tests:

```bash
python -m pytest tests/ -q        # 50 tests, no graph/LLM/cost needed
```

## Status

Design complete (**all map tickets resolved**) and the **MVP walking skeleton is built — 50 tests
green**. All logic that can be proven without spend is locked; what remains is a live run
(`docker up` + key, real Cypher + LLM) and more year-one entries for a fuller demo. Deeper notes:
[`docs/ENGINEERING-HANDBOOK.md`](docs/ENGINEERING-HANDBOOK.md).
