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

## Findings — first real run (2026-07 pause point)

Ran on 3 real entries (2024-01-06 [4 pages], 2025-01-03, 2025-09-17). Pipeline works
end-to-end; dates + bi-temporal windows correct; dedup works (people appear once).

**Fidelity problems found (this is the prototype earning its keep):**
1. **No author/"self" node** — first-person entries produced NO node for the writer, so edges
   that should start from the author wired between random concepts
   (`Meditation —STRUGGLES_WITH→ Uppa`). → **Fixed** by anchoring each episode with
   "written by <subject>; I/me/my = <subject>" (`MIRROR_SUBJECT_NAME`). Not yet re-validated
   (quota wall hit before a clean re-run).
2. **Emotional content collapsed into edge text, not nodes** — "angry/annoyed/effort not to get
   angry" never became `Struggle`/`EmotionalState` entities, so they're not trackable over time.
   Needs ontology-guidance work + a stronger model. STILL OPEN.
3. **Ran on the weak model** — `gemini-3-flash-preview` was 503-overloaded, so extraction fell to
   `gemini-3.1-flash-lite`, which is weak for nuanced extraction. Quality ceiling.

**Provider reality (affects [[08-mvp-scope-sequencing]]):** Gemini **free tier can't sustain
iterative dev** — 503s on the newest model + 429 rate limits after ~8 runs. Real dev needs
pay-as-you-go (pennies at this scale) or a local model. Harness is now resilient (fallback chain,
network-drop handling, in-place model swap, `MIRROR_MAX_ENTRIES` for cheap validation).

**Next when resumed:** ensure quota (billing or reset) → re-run (optionally `MIRROR_MAX_ENTRIES=1`)
→ confirm the author anchor produces `<subject> —PRACTICES→ Meditation` etc. → then tackle
finding #2 (get Struggle/EmotionalState nodes) with better ontology descriptions + a stronger model.
