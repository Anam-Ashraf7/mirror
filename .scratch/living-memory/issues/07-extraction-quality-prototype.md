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

## Findings — session 2 (2026-07, provider switch + extraction tuning + model bake-off)

**Crown jewel PROVEN.** Real handwritten entries → a coherent, correctly-typed, **bi-temporal**
self-graph. A genuine "then→now" fired: `anger —TriggeredBy→ uppa` valid 2024-01-06 → invalidated
2025-01-03, and `anger —ShiftedTo→ deeper connection`. This is exactly what the whole project is for.

**Provider abstraction shipped** (`mirror/providers.py`): `MIRROR_LLM_PROVIDER=gemini|openai|
openai_generic` swaps the whole LLM+embedder+reranker trio via `.env`, no code edit — leans on
Graphiti's own clients (ticket 05 decision), no extra SDK. `openai_generic`+`base_url` reaches
anyone OpenAI-compatible. Per-run token+cost reporting added.

**The two extraction problems and their fixes (all transfer across models):**
1. *Type drift → open-vocab edges* (`WANTS_TO_IMPROVE`, `CREATED`). Fixed by (a) sharpened
   entity/edge docstrings — Graphiti feeds them to the prompt — and (b) `custom_extraction_
   instructions` ("use ONLY these 8 relations; never invent names") + a complete `EDGE_TYPE_MAP`
   (added the `Intends` edge for orphaned Intention edges). Result: **100% typed, zero drift.**
2. *Missing nodes + wrong subject/direction.* Sharpened descriptions restored recall (emotions,
   struggles, insights, intentions). A subject/direction instruction ("the experiencer is always
   Anam; 'Dear Master' is the addressee, not the subject; a feeling is `TriggeredBy` a person, not
   the reverse") fixed a mis-attribution where the addressee "Master" was cast as the experiencer.

**Model bake-off (same improved pipeline, primary-sourced prices):**
- **gpt-5.4-nano** ($0.20/$1.25; ~$0.01/entry): best emotions + `ShiftedTo` transitions; **drops
  Insights stochastically** (v2 caught 4, v3 caught 0 — same config → it's VARIANCE, not tier).
- **gpt-5.4-mini** ($0.75/$4.50; ~$0.04/entry): reliable Insights but **muddles emotions**
  ("felt peace"→anger node) and fired **no** transitions. Not worth 4× — differently-flawed.
- **Gemini 3 Flash**: **untestable** — free-tier 503 is server capacity, a *fresh free key does
  not help*; needs the $10 prepay. (OpenAI is also prepaid, $5 min; both non-refundable, 1yr.)
- Reasoning knob: for this structured task **`low` beats `medium`/`none`** — more reasoning made
  nano freelance open-vocab edges; `none` failed to attach edges.

**Decision — extraction config (option #1):** the residual gap is *variance*, not model tier, so
we don't pay up. **nano + ENSEMBLE (ingest each entry N× ) + post-dedup.** The union recovers full
recall (all layers together); a Cypher cleanup collapses the duplicate edges the union leaves
(`MIRROR_ENSEMBLE_PASSES`, `dedupe_graph()`). Validated on entry 1 ×2: full recall, 0 duplicate
edges, ~$0.03/entry. Residual (left for the build): near-duplicate *nodes* ("listen to my heart" vs
"I need to listen to my heart") need semantic entity-resolution tuning, not a string merge.

**Env realities:** new OpenAI accounts are **Tier-1** (low RPM/TPM — high `SEMAPHORE_LIMIT` triggers
429 backoff; keep it ~2); long runs get killed in this environment, so the full-3-entry ensemble
needs gentle concurrency + chunking. Costs measured, not guessed: early/near-empty graph ≈
$0.005/entry, rises with graph size; whole 3-yr corpus is single-digit dollars even with iteration.
