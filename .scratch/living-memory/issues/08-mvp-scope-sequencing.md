# MVP scope & build sequencing

Type: grilling
Status: open
Blocked by: 02, 03, 07

## Question

Define the first shippable slice of the core engine and the phase order to get there — the last
decision before the spec is build-ready.

Resolve:
- The minimal end-to-end path: capture → proofread gate → ingest → one real longitudinal question
  answered with citations.
- What's in v1 vs deferred (reflection engine per ticket 02; rollups already out of scope).
- Build order and the checkpoints that prove each phase works.

Blocked until reflection-engine timing (02), interaction surface (03), and the extraction-quality
prototype (07) are known — scope can't be honest without them.

## Decisions so far (MVP grill — in progress, 2026-07)

Blockers cleared: 07 proved the crown jewel; 02 (reflection = phase-two) and 03 (local web app)
resolved. Grilling the MVP one thread at a time. Settled threads:

### Thread 1 — ingest identity: the graph is a derived cache, entries are the source of truth

The prototype wipes the graph every run (`clear_graph`, fine for a fidelity harness, fatal for a
memory meant to accumulate over 3 years). Grilled what "add today's entry" and "fix a typo in an
old entry" actually mean. Settled:

- **No wipe-on-run.** The graph accumulates. Re-running must not duplicate an already-ingested entry.
- **Entry identity is EXACT and deterministic** — date + a content hash of the proofread text.
  **Not** fuzzy/"almost similar": two calm evenings a year apart read nearly identical, and a fuzzy
  entry-match would silently eat a real distinct day. Fuzziness belongs one level down, at *nodes*
  ("this anger = that anger"), which Graphiti already handles. **Exact for entries, fuzzy for
  concepts — never cross them.**
- **Proofread entries `{date, text}` are the source of truth (sacred); the graph is a derived,
  rebuildable cache.** → [[10-codebase-design-for-agents]] makes this a module boundary (EntryStore
  vs graph).
- **Editing an entry = re-derive that entry and everything after it**, oldest-first (Graphiti has
  `remove_episode(uuid)` — deletes the edges an episode created + nodes only it mentioned — so
  remove-then-re-ingest works). **No cheap "patch just this one episode" mode.** Reason (the trap
  the grill caught): the graph is a *function of all entries in order*, so a lone re-add of an old
  episode recreates its facts **fresh and un-invalidated** while the later entry that invalidated
  them isn't re-run — silently un-doing a real then→now transition (e.g. `anger —TriggeredBy→ uppa`
  invalidated in 2025 comes back valid when you fix a 2024 typo). Re-derive-forward is the only
  correct version; it's affordable (whole corpus re-extracts for single-digit dollars, 07) and old
  edits are **rare**, so the cheap-but-wrong mode isn't worth building.

### Thread 2 — walking-skeleton scope (in progress)

- **No capture UI in v1.** We already have proofread transcripts in `data/transcripts/`; v1 seeds
  EntryStore from those and spends its whole budget on the ASK path. Photo→transcribe and the
  proofread-gate UI are v2 (typed/proofread text needs no transcription → nothing to proofread).
- **Target question (the skeleton's success test):** *"What did I struggle with most, and where is
  it now?"* Decomposes into **Ranking** (most) → **Transitions** (where is it now). Deterministic
  underneath; LLM only narrates + cites.
- **"Most" metric:** count of **distinct entries per year** a struggle appears in → compute the top
  struggle **per year** → synthesize across years into the answer. Not year-one-scoped; "most" can
  range over any window.
- **Ask-path stance = transparency + correction (fork A∪B).** Show the **grouped** struggles with
  per-year entry counts AND the underlying elements (the real entries/facts); the LLM gives its
  read; the **user sees the data, judges, and corrects** — and corrections are a signal that
  improves the system. Machine proposes, user is the authority. No claim without citation.

**The scatter finding (checked against real prototype data — and one honest correction).** A single
theme — "anger" — is smeared across the graph, which breaks naive ranking. BUT be precise about
which parts are real (this was overstated at first):
- **Same-type wording dupes are mostly NOT a within-graph problem.** The three wordings I first
  cited (`holding a lot of anger and annoyance` / `holding anger and annoyance` / `Persistent anger
  and annoyance`) came from *three different runs* (Gemini + two nano), pooled — they did not
  coexist in one graph. Graphiti's `add_episode` already runs an **LLM+embedding dedup pass**
  (`resolve_extracted_nodes`) that merges obvious same-type dupes against the existing graph. The
  residual same-type risk is **cross-entry drift over 3 years**, which Graphiti handles imperfectly
  → tune its dedup (better prompt / canonical vocab), don't hand-roll it.
- **Cross-type scatter IS real and Graphiti won't fix it (by design):** `anger` [EmotionalState]
  *and* `holding anger` [Struggle] are legitimately different types, so Graphiti won't merge them —
  yet they're the same theme. The trigger (`uppa`/`Madhav`) landed on the feeling in the nano run,
  on the struggle in the Gemini run; the transition `anger —ShiftedTo→ deeper connection` landed
  only on the feeling. A query tracing just the *Struggle* node to answer "where is it now?"
  **misses** the transition. This cross-type + scattered-edge gathering is the genuine gap.
- Same class elsewhere: `listen to my heart` filed as both Intention and Insight; `smile more` as
  both Intention and EmotionalState; `Intention` couldn't attach to the `Struggle` it heals.

**Grounding note (honesty):** the Intention↔Struggle example is real in the data — Intention
*"Celebrate achievements before suggesting improvements"* ↔ Struggle *"Difficulty appreciating
others' work"* (same theme). (An earlier "smile more heals impatience" example was invented and
retracted.) That `Addresses` edge was never actually extracted (ontology didn't allow it until now),
so "the edge will form" is a **hypothesis to validate on the next run**, not a proven result.

**Decision — split by destructive-vs-not, which incorporates the "clean the structure before
ingest" idea rather than replacing it:**
- **Ingest time — SAME-TYPE dedup:** let Graphiti's existing `resolve_extracted_nodes` do it (it
  already does); **tune** it (dedup prompt / canonical vocab) rather than hand-rolling a second LLM
  pass. Rationale: merging is **destructive + permanent** (a wrong merge needs a re-derive) and adds
  a stochastic call — so only do it for *high-confidence same-type* dupes, where Graphiti is strong.
- **Extraction time — the missing structural link (done):** **reuse `Addresses` for `Intention →
  Addresses → Struggle`** (no new edge type = minimal drift). Genuine new info from the text.
- **Query time — CROSS-TYPE gathering (`ThemeResolver`, build with MVP):** a **non-destructive**
  view that unifies feeling + struggle into one canonical **theme** and pulls everything off any of
  its nodes (per-year counts, triggers, transitions) regardless of type/attachment. Deterministic,
  **testable with fixtures**, cheap to improve, never re-derives, and it's exactly what the
  transparency/correction UI shows the user. **The target question rides on `ThemeResolver`.**
  → design lives with [[10-codebase-design-for-agents]] as a module.
- Rejected: an EmotionalState→Struggle "manifests" bridge at extraction (fragile, re-opens drift);
  and aggressive permanent merging at ingest (a wrong fuse of `anger`/`annoyance` can't be undone
  without a re-derive).
- Bonus (post-v1): because the structure is visible before `SAVE`, we *could* offer a "proofread the
  graph" gate — show what's about to enter memory, let the user correct it — extending the
  proofread-gate principle from transcript to graph.

### Thread 3 — v1 primitives + build order (SETTLED)

- **v1 analytical primitives = Ranking + Transitions only.** Timeline / CoOccurrence deferred.
- **Build order — five thin phases, each gated by a checkpoint:**
  0. **EntryStore** (source of truth; exact date-identity + hash-version) → re-add is a no-op.
  1. **extraction** module — harden the prototype: **no-wipe, incremental**, tuned ingest-dedup.
  2. **ThemeResolver** — deterministic cross-type theme view, fixture-tested.
  3. **MemoryEngine.ask()** — Ranking → Transitions → LLM narrates + cites.
  4. **web** — FastAPI + minimal browser page (three-layer cited answer + correction affordance).
  - Whole-skeleton success = phase-4 checkpoint (target question answered end-to-end, cited) on
    real data. Deep-module discipline throughout ([[10-codebase-design-for-agents]]).
- **Data caveat (affects the demo, not the build):** only one year-one entry exists today
  (2024-01-06), so "most in year one" is thin until more year-one transcripts are added. A new
  `data/entries/2026-05-19.jpeg` is present but not yet transcribed.

## Build progress

- ✅ **Phase 0 — EntryStore** (`mirror/entry_store.py`, `tests/test_entry_store.py`, 13 tests green).
  Pure, no LLM/graph. Locks the entry-identity decisions from Thread 1.
- ✅ **Phase 1 — extraction/derive logic** (`mirror/extraction.py`, `tests/test_extraction_plan.py`,
  12 tests green). Pure `plan_sync` locks re-derive-forward (idempotent no-op / edit / backfill /
  deletion) + self-describing episode names (`journal-<date>-<hash12>`). `GraphDeriver` is the I/O
  shell (no-wipe, incremental, ensemble + edge-dedup reused from the prototype). **Live wiring
  against FalkorDB+LLM is written but validated on the first real `docker up` + key run** — not
  exercised in this environment (would spend + touch real entries).
- ✅ **Phase 2 — ThemeResolver** (`mirror/theme_resolver.py`, `tests/test_theme_resolver.py`,
  11 tests green). Pure, deterministic, non-destructive cross-type theme view: unifies the anger
  feeling + struggle + wordings into one theme, per-year distinct-entry counts, "where is it now"
  from bi-temporal windows. Guardrails: no filler-word chaining; synonym limit documented (a
  passing test), left to the user-correction loop.
- ✅ **Phase 3 — MemoryEngine + primitives** (`mirror/primitives.py`, `mirror/engine.py`,
  `tests/test_primitives.py` + `tests/test_engine.py`, 13 tests green). Pure Ranking+Transitions →
  cited `Answer` + deterministic grounded renderer (LLM only *rephrases*, never adds facts; refuses
  when nothing found). Facade `ingest()`/`ask()` hides Graphiti; glue validated against a fake
  graph. Live graph/LLM validated on a real run.
- ✅ **Phase 4 — web** (`mirror/web/app.py` + `index.html`, `tests/test_web.py`, 5 tests green).
  FastAPI + one calm browser page: ask box → grounded narrative, per-year ranking, "where is it
  now" chip, the grouped-themes transparency panel ("correct me if I'm wrong"), cited entries, and
  a correction box (`/api/correction` → `data/corrections.jsonl`, the v1 correction-signal stub).
  Talks ONLY to MemoryEngine. Routes validated against a fake engine.

**Walking skeleton COMPLETE — 50 tests green.** All correctness that can be proven without spend is
locked (identity, re-derive-forward, theme resolution, ranking/transitions, rendering, routes).
Run live: `docker compose up -d` → set `.env` (provider + key) → `pip install -r requirements.txt`
→ `python -m mirror.transcribe` (+ proofread) → `uvicorn mirror.web.app:app` → open localhost, click
"Sync graph from entries", then ask. **Phase-4 checkpoint (target question answered end-to-end,
cited, in the browser) awaits that live run + more year-one entries for a non-thin demo.**

## Status: grill resolved; MVP walking skeleton built. Remaining is live validation + data.

## Still open

- How the correction signal (Thread 2) is captured/stored and fed back to improve the system —
  design when we reach Phase 3/4.
