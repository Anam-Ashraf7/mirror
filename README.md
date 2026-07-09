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
| Extraction | **Gemini 2.5 Pro** (also reads handwriting from page photos) |
| Embeddings | **Gemini** (single vendor) |
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

# drop a few real entries in data/entries/, one file each, named by date:
#   data/entries/2023-03-12.md
#   data/entries/2024-11-03.md
#   data/entries/2026-04-21.md

python -m mirror.prototype        # ingest oldest-first, then print the graph
```

`data/` is git-ignored — your journal entries stay local.

## Status

Design is ~complete: **7 of 9** map tickets resolved. Remaining are gated on running
this prototype with a few real entries — then the MVP scope/sequence gets locked and
the build begins.
