# Extraction-quality prototype on real entries

Type: prototype
Status: open
Blocked by: — (awaiting user-provided entries: 3–5 real journal entries with dates,
typed or photographed, spread across the ~3 years)

## Question

De-risk the whole idea empirically before committing to a build. Take a handful of **real**
journal entries (a few transcribed notebook pages, oldest-first), run them through
Gemini-2.5-Pro extraction with the approved ontology into a throwaway FalkorDB/Graphiti graph,
and judge fidelity **with the user**:
- Does the graph faithfully represent what the entries actually say?
- Are Struggles / Practices / EmotionalStates / Insights tagged the way the user recognises them?
- Do dates land as `reference_time` correctly, and does a two-entry `SHIFTED_TO` transition form?
- Where does extraction hallucinate, miss, or mis-bucket?

Rough script, not production. Links the prototype + a short findings note as assets. This is the
single highest-value early ticket — it tells us if the crown jewel actually works.

## Progress (harness scaffolded — awaiting entries + a run)

The runnable harness is built and committed, so running is one command once entries exist:
- `mirror/ontology.py` — approved person-ontology as Graphiti custom Pydantic types (coarse
  `Literal` buckets; no protected `name` attribute; entity/edge/edge-type-map registries).
- `mirror/prototype.py` — connects Gemini 2.5 Pro + Gemini embeddings + FalkorDB, ingests
  `data/entries/YYYY-MM-DD.md` **oldest-first** with `reference_time` = authored date, then dumps
  the resulting entities/edges (with bi-temporal windows) for the fidelity eyeball.
- `docker-compose.yml`, `requirements.txt`, `.env.example`, `README.md` — the run recipe.

Still **open**: needs 3–5 real entries in `data/entries/` + `docker compose up` + a Gemini key,
then we run it, judge fidelity together, and probe the ticket-06 drift risks.
