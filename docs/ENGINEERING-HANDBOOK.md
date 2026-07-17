# mirror — Engineering Handbook

> A durable, in-depth record of **what mirror is, every decision behind it, every problem we hit
> and how we solved it, and how the whole thing actually works.** Written so that reading this
> top-to-bottom gives you a deep, first-principles understanding of your own system — not a
> changelog, but the reasoning underneath it.
>
> Canonical, always-current source of decisions lives in the wayfinder workspace
> (`.scratch/living-memory/map.md` + `issues/*.md`). This handbook *narrates and explains* that;
> when the two disagree, the map wins. Last synced: 2026-07-17.

---

## 0. TL;DR

**mirror** turns ~3 years of handwritten meditation-journal entries into a **temporal knowledge
graph of yourself** that answers longitudinal questions — *"how have I changed in 3 years?"*,
*"what did I struggle with most, and where is it now?"*, *"what patterns am I too close to see?"* —
with **every answer grounded in what you actually wrote**, never invented.

The hard, de-risked, **proven** capability ("the crown jewel"): real entries produce a correctly
typed, **bi-temporal** self-graph in which a *then → now* change fires on its own — e.g. an anger
that was triggered by a person in a 2024 entry is automatically **invalidated** by a 2025 entry
where that anger is gone. That is the whole product, and it works.

---

## 1. The vision & why it's shaped this way

You journal, but you can't *read back* 3 years of notebooks — you're too close to see your own
patterns. mirror is the memory you can't hold in your head: feed it entries, ask it hard questions
about your own change over time, and get answers that always point back to the specific day you
wrote something.

Two non-negotiables flow from that:

1. **Grounded, never invented.** The LLM *narrates* facts pulled from the graph; it never makes up
   a plausible story. Every answer cites source entries.
2. **Trust in the data is the product.** Every source (photo transcript, audio transcript) is
   **proofread and confirmed by you before it enters the graph** ("the proofread gate"). What you
   wrote is sacred and kept apart from anything the machine merely *inferred*.

---

## 2. Architecture at a glance

### Stack
- **Runtime:** Python (Graphiti is a Python library).
- **Knowledge-graph framework:** **Graphiti** (self-hosted) — does the LLM extraction *and* layers
  a **bi-temporal** fact model (valid-time + transaction-time) in software.
- **Graph database:** **FalkorDB** in Docker (one backend from laptop to prod; ports 6379 + 3000).
- **Extraction/embeddings:** pluggable per `.env` — Google Gemini, OpenAI, or any OpenAI-compatible
  endpoint. Currently OpenAI `gpt-5.4-nano`.

### The ~7 deep modules (see [ticket 10](../.scratch/living-memory/issues/10-codebase-design-for-agents.md))
| Module | Role | Status |
|---|---|---|
| **EntryStore** (`entry_store.py`) | Source of truth: proofread `{date, text}`, content-addressed, exact identity. Graph is derived from it. | ✅ built, 13 tests |
| **extraction** (`extraction.py`) | entry → typed facts; no-wipe incremental sync + re-derive-forward. Ensemble + dedup. | ✅ built, 12 tests (live wiring pending a real run) |
| **ThemeResolver** (`theme_resolver.py`) | Deterministic, non-destructive cross-type theme view. | ✅ built, 11 tests |
| **primitives** (`primitives.py`) | Ranking + Transitions → grounded, cited `Answer` + renderer. | ✅ built (in the 13 below) |
| **MemoryEngine** (`engine.py`) | THE facade: `ingest()`, `ask()`. Hides Graphiti entirely. | ✅ built, 13 tests (glue vs fake graph) |
| **web** (`web/app.py` + `index.html`) | FastAPI + browser UI. Talks *only* to MemoryEngine. | ✅ built, 5 tests |
| **ontology** (`ontology.py`) | The typed person-ontology that steers extraction. | ✅ done |
| **providers** (`providers.py`) | LLM/embedder/reranker chosen by `.env`. | ✅ done |
| **Transcriber** (`transcribe.py`) | photo → text (audio planned). One swappable seam. | photo done |

> **MVP walking skeleton is built — 50 tests green, zero spend.** Every decision that can be wrong
> in *logic* (identity, re-derive-forward, theme grouping, ranking/transitions, rendering, routes)
> is locked with pure/glue tests. What remains is *live* validation (the real Cypher + LLM against
> FalkorDB, exercised on `docker up` + a key) and richer year-one data for a non-thin demo. See
> [ticket 08](../.scratch/living-memory/issues/08-mvp-scope-sequencing.md) for the phase-by-phase
> build log.

### Data flow (target)
```
notebook photo ─┐
typed entry ────┼─► Normalizer ─► {date, text} ─► [PROOFREAD GATE] ─► EntryStore (source of truth)
audio ──────────┘                                                          │
                                                                           ▼
                                              extraction (ensemble ×N ─► dedup) ─► Graphiti/FalkorDB
                                                                           │        (DERIVED cache)
                                                    ask(question) ◄── MemoryEngine ◄┘
                                                         │
                                              narrative + transition timeline + CITED entries
```

---

## 3. The big decisions and *why* (with the alternatives we rejected)

Each is a resolved wayfinder ticket; the reasoning is summarized here.

### 3.1 Substrate = a temporal knowledge graph (Graphiti), not a vector store or plain DB
"Then vs now" is the core question, so the system must represent **facts that change over time**.
Graphiti's **bi-temporal** model (when something was true in your life *vs* when the system learned
it) is exactly that. A pure RAG/vector store can retrieve similar passages but can't *reason about
change*; a plain graph DB has no notion of a fact becoming invalid.

### 3.2 Is there a native bi-temporal *graph* database? — research finding: effectively no
We researched this from primary sources (see `.scratch/living-memory/assets/bitemporal-database-landscape.md`):
- **XTDB** is the only truly *native* bi-temporal database — but it's document/SQL, **not** a
  property graph.
- **TerminusDB** = partial (version-control / transaction-time). **TypeDB, Datomic** = not native
  bitemporal.
- Conclusion: no native bi-temporal graph DB exists. **Graphiti adds bitemporality in software
  *and* does the extraction**, so it gives us both; XTDB would give storage only. → **Stay on
  Graphiti.**

### 3.3 Graph backend = FalkorDB
One backend from laptop to production (single Docker container), no migration later. Kuzu is
deprecated in Graphiti; Neo4j rejected as heavier. (Ticket in map's locked constraints.)

### 3.4 Representation = hybrid (typed ontology + open extraction + raw-entry embeddings)
- A curated **typed person-ontology** (below) for the aspects we track consistently across years.
- Graphiti's **open-ended** extraction running alongside, so anything the ontology doesn't name is
  still captured as a generic `Entity`.
- Raw entries embedded for RAG fallback.
This buys cross-year consistency *without* throwing away the unexpected.

### 3.5 The person-ontology (`mirror/ontology.py`)
Anchored on a single **Subject** node (you, "Anam").
- **Entities:** `Struggle`, `Practice`, `EmotionalState`, `Insight`, `Relationship`, `Intention`.
- **Edges:** `StrugglesWith`, `Practices`, `Experiences`, `Realized`, `TriggeredBy`, `Addresses`,
  `Intends`, `ShiftedTo`.
- **Design rules baked in:**
  - **Coarse `Literal` buckets** (e.g. intensity `subtle|moderate|strong`), never numeric scores —
    a cheap model can apply a 3-way label consistently across 3 years; it cannot pick "6 vs 7".
  - **No `name` attribute** on any entity — `name` is reserved by Graphiti's `EntityNode`. We only
    add *extra* atomic attributes.
  - **Docstrings are extraction rules, not decoration** — Graphiti feeds each entity/edge docstring
    straight into the extraction prompt. They're written with concrete triggers/examples. This is
    the primary lever that makes a *cheap* model reliably create `EmotionalState`/`Struggle`/
    `Insight`/`Intention` nodes instead of burying them in free text.

### 3.6 Extraction LLM & provider strategy + the billing realities we learned the hard way
Originally Gemini Flash (multimodal, so it doubles as handwriting OCR). Then we hit reality and
switched the *default* to OpenAI `gpt-5.4-nano`, behind a provider switch so it doesn't matter.

Billing lessons (both providers, from India, 2026 — **primary-sourced**):
- **Both Gemini and OpenAI are PREPAID** in some regions (incl. India). You buy credits up front;
  they're **non-refundable** and expire (~1 yr). OpenAI min **$5**, Gemini min **$10**.
- **Enabling billing without buying credits makes things *worse*** — it drops you off the free tier
  and every call 429s with *"prepayment credits are depleted."* (We hit this live.)
- **A fresh free Gemini key does NOT bypass a 503** — 503 is *server capacity* on the newest model,
  not a per-key quota. Only prepay + a stable model avoids it.
- **New paid OpenAI accounts are Tier-1** — low RPM/TPM; high concurrency triggers 429 backoff.
- OpenAI current-gen list prices (USD / 1M in-out, from developers.openai.com): `gpt-5.4-nano`
  0.20/1.25 · `gpt-5.4-mini` 0.75/4.50 · `gpt-5.6-luna` 1/6 · `gpt-5.4` 2.50/15. All GPT-5.x are
  multimodal. Older GPT-4o/4.1/o-series are off the current pricing page.
- (Fuller landscape incl. DeepSeek/GLM/Ollama in `.scratch/living-memory/assets/05-llm-provider-landscape.md`.)

### 3.7 The provider abstraction (`mirror/providers.py`) — how it works
We did **not** build a new multi-provider SDK. We **lean on Graphiti's own pluggable client system**
(ticket 05: "lean on Graphiti's provider system; wrap only the gaps"). One factory picks the trio:
- `MIRROR_LLM_PROVIDER = gemini | openai | openai_generic` selects everything.
- `openai_generic` + `MIRROR_LLM_BASE_URL` reaches **anyone** OpenAI-compatible (DeepSeek,
  OpenRouter, Ollama, LiteLLM) — the one-flip local-extraction escape hatch.
- Every model id and key is read from `.env`, so trying a new model/provider **never touches code**.
- Accepts both `OPENAI_API_KEY` and `OPEN_AI_API_KEY` spellings.
- Per-run token + **cost** reporting via `PRICES` + `cost_for()`.
- OpenAI branch pins `reasoning="low"` (env-overridable) — see §4.6.

---

## 4. The extraction-quality journey — every problem and its fix

This is the heart of the work. The prototype's *entire job* was to earn its keep by finding where
extraction lies, so we could fix it before building. It did. Chronologically:

### 4.1 Problem: no author / "self" node → edges wired between random concepts
First-person entries produced **no node for the writer**, so edges that should start at the author
wired between unrelated concepts (e.g. `Meditation —STRUGGLES_WITH→ Uppa`).
**Fix:** anchor each episode with a framing line — *"Journal entry written by Anam; throughout
I/me/my refer to Anam"* (`MIRROR_SUBJECT_NAME`) — plus the subject pin in the custom instructions.

### 4.2 Problem: emotional content collapsed into edge text, not nodes
"angry / annoyed / effort not to get angry" never became `EmotionalState`/`Struggle` nodes, so they
weren't trackable over time.
**Fix:** rewrote ontology docstrings as explicit extraction rules with triggers ("ALWAYS create a
distinct node for each named feeling; NEVER fold a feeling into another node's description"). Recall
of emotions/struggles/insights/intentions restored.

### 4.3 Problem: type drift → open-vocabulary edges
Cheap models freelanced relation names (`WANTS_TO_IMPROVE`, `CREATED`) instead of using our 8.
**Fix, three levers together:**
1. Sharpened edge docstrings.
2. `custom_extraction_instructions` (passed to `add_episode`, injected into **both** node and edge
   prompts): *"use ONLY these 8 relations; follow the direction exactly; never invent names."*
3. A **complete `EDGE_TYPE_MAP`** covering every entity pair we care about (incl. an added `Intends`
   edge for orphaned Intention edges), so the model always has a valid typed option and never needs
   to freelance.
**Result: 100% typed, zero drift.**

### 4.4 Problem: wrong subject / reversed edge direction
A mis-attribution cast the *addressee* ("Dear Master") as the experiencer, and some edges pointed
backwards (`person —TriggeredBy→ feeling`).
**Fix:** subject/direction pinning in the custom instructions — *"the experiencer is always Anam;
'Master' is the addressee, not the subject; a feeling is `TriggeredBy` a person, not the reverse;
model 'angry at X' as an EmotionalState Anam Experiences, TriggeredBy X."*

### 4.5 Problem: **variance is the real enemy** (not model tier)
Same model, same entry, same config, run twice → **different results** (one run catches an Insight,
the next drops it). We proved this is *stochasticity*, not a too-weak model:
- `gpt-5.4-nano`: best at emotions + `ShiftedTo` transitions, but **drops Insights randomly** (v2
  caught 4, v3 caught 0 — identical config).
- `gpt-5.4-mini` (4× the cost): reliable Insights but **muddles emotions** ("felt peace" → anger
  node) and fired **no** transitions. Differently flawed, not better.
- Bigger ≠ better. The enemy is variance.
**Fix — the ensemble technique (`MIRROR_ENSEMBLE_PASSES`):** ingest each entry **N times**;
Graphiti's entity resolution merges the overlap (`SAME_AS` components) while the **union** of what
each pass caught survives → full recall from a cheap model. All passes share the entry's
`reference_time`, so bi-temporal ordering is untouched. Costs ~N× tokens (still cents on nano).

### 4.6 Problem: ensemble leaves **duplicate edges**
Graphiti dedups *nodes* well but *facts* poorly across near-identical re-ingestions, so the union
leaves the same `(source, relation, target)` edge multiple times.
**Fix — `dedupe_graph()`:** a Cypher post-pass that collapses each duplicate `RELATES_TO` group to
one edge, **preferring to keep a bi-temporally-invalidated edge** (`ORDER BY e.invalid_at DESC`) so
the then→now windows survive. Validated: removed the dups, 0 remained.

### 4.7 Finding: reasoning effort `low` beats `medium`/`none` for this task
GPT-5 reasoning models reject Graphiti's default `effort='minimal'` (nano errors 400). Among the
valid levels, **`low` wins**: more reasoning made nano *freelance* open-vocab edges; `none` failed
to attach edges at all. Pinned `reasoning="low"` (env: `MIRROR_OPENAI_REASONING`).

### 4.8 The decision that came out of it (extraction config, "option #1")
Since the residual gap is **variance, not tier, we don't pay up.** Config =
**`gpt-5.4-nano` + ensemble (N passes) + `dedupe_graph()`**. Validated on a real entry ×2: full
recall across all layers, 0 duplicate edges, **~$0.03/entry**.
**Residual (deferred to the build):** near-duplicate *nodes* with different wording ("listen to my
heart" vs "I need to listen to my heart") need semantic entity-resolution tuning — a string merge
is unsafe, so it's left for the real build, not the prototype.

---

## 5. Operational gotchas & how we solved them

These are the un-glamorous things that cost real time; documented so you never re-debug them.

- **503 "overloaded" on the newest model** → a **model fallback chain** (`MIRROR_LLM_MODEL` can be
  comma-separated). On a transient error the ingest loop **switches the live model in place**
  (no graph wipe, no wait) and retries; only on the last model does it back off. The index persists
  across entries.
- **Transient-error detection must check exception *type*, not just message** — Graphiti buries the
  real cause (a 503 or a network `ReadError`) inside a bare, message-less `Exception`. `_is_transient()`
  walks the `__cause__/__context__` chain and matches both text (`503`, `429`, `RESOURCE_EXHAUSTED`,
  "overloaded", "Connection error") **and** type names (`APIConnectionError`, `RateLimitError`,
  `ConnectError`, `ReadTimeout`, …).
- **Tier-1 rate limits** → keep **`SEMAPHORE_LIMIT` low (~1–2)**; must be set **before** `graphiti_core`
  is imported (it reads it at import). High concurrency just gets you throttled — *slow is faster*.
- **Windows console crashes on arrows/bullets** (cp1252) → `sys.stdout.reconfigure(encoding="utf-8")`
  at startup.
- **Cheap validation knobs:** `MIRROR_MAX_ENTRIES=1` (ingest just the first entry) and
  `MIRROR_ENSEMBLE_PASSES` let you test the pipeline for cents.
- **Prepaid quota walls:** see §3.6 — the fix is *buy credits*, not *toggle billing*.
- **Pushing to GitHub** uses SSH host alias `git@github-personal` → `~/.ssh/id_ed25519`
  (passphrase-protected). If push fails with `Permission denied (publickey)`, the ssh-agent isn't
  loaded — start it and `ssh-add` the key, then push. **Reminder: rotate any API key that has ever
  appeared in a chat or a commit.**

---

## 6. MVP decisions from the grilling sessions

The prototype phase closed; we're grilling the MVP scope one thread at a time
([ticket 08](../.scratch/living-memory/issues/08-mvp-scope-sequencing.md)).

### Thread 1 — SETTLED: the graph is a derived cache; entries are the source of truth
The prototype wipes the graph every run — fine for a fidelity harness, **fatal** for a memory meant
to accumulate over 3 years. Resolved:
- **No wipe-on-run.** The graph accumulates; re-running must not duplicate an ingested entry.
- **Entry identity is EXACT and deterministic** (date + content hash of the proofread text), **not
  fuzzy.** Two calm evenings a year apart read nearly identical; a fuzzy entry-match would silently
  eat a real distinct day. *Exact for entries, fuzzy for concepts (nodes) — never cross them.*
- **Proofread `{date, text}` = source of truth (sacred); the graph = derived, rebuildable cache.**
  This is a **module boundary** (EntryStore vs graph), which is what makes the next point safe.
- **Editing an entry = re-derive that entry and everything after it**, oldest-first (Graphiti's
  `remove_episode(uuid)` deletes the edges an episode created + nodes only it mentioned, so
  remove-then-re-ingest works). **No cheap "patch one episode" mode.**
  - **The trap that forces this:** the graph is a *function of all entries in order*. A lone re-add
    of an old episode recreates its facts **fresh and un-invalidated**, while the later entry that
    invalidated them isn't re-run — silently **un-doing a real then→now transition** (fix a 2024
    typo → a 2025 invalidation vanishes). Re-derive-forward is the only correct version; it's cheap
    (whole corpus re-extracts for single-digit dollars) and old edits are rare.

### Thread 2 — IN PROGRESS: the walking-skeleton scope
Open: thinnest end-to-end slice (typed-only first, or full photo→proofread→ingest?); which
analytical primitives ship in v1 (Timeline / Transitions / Ranking / CoOccurrence) vs raw-graph
only; build order + the checkpoint that proves each phase.

---

## 7. Codebase discipline — deep modules for AI agents
Full rationale in [ticket 10](../.scratch/living-memory/issues/10-codebase-design-for-agents.md).
In one breath: **a few deep, sealed modules, not a web of shallow ones.** I own each module's
interface; an agent can fill the implementation; **tests lock the behavior** so the box stays
closed. The app never imports Graphiti/FalkorDB directly — only `MemoryEngine`. Source of truth
(EntryStore) is split from derived state (the graph), and derived state is always rebuildable.

---

## 8. Costs (measured, not guessed)
- Near-empty graph: **≈ $0.005/entry**; rises with graph size.
- `gpt-5.4-nano` ensemble ×2 + dedup: **≈ $0.03/entry** with full recall.
- **The whole 3-year corpus is single-digit dollars** — even with re-derivations and iteration.
  This affordability is *why* re-derive-forward (§6) is viable.

---

## 9. How to run it
```bash
# 1. start FalkorDB
docker compose up -d
# 2. configure (never commit real .env)
cp .env.example .env    # set MIRROR_LLM_PROVIDER + the provider's API key
# 3. deps
pip install -r requirements.txt
# 4. (photos) transcribe handwriting -> data/transcripts/*.md, then PROOFREAD them
python -m mirror.transcribe
# 5. ingest the proofread transcripts + dump the graph for the fidelity eyeball
PYTHONPATH="$(pwd)" python -u -m mirror.prototype
```
Useful env: `MIRROR_LLM_PROVIDER`, `MIRROR_LLM_MODEL`, `MIRROR_ENSEMBLE_PASSES`, `MIRROR_MAX_ENTRIES`,
`MIRROR_OPENAI_REASONING`, `SEMAPHORE_LIMIT`, `MIRROR_SUBJECT_NAME`, `FALKORDB_*`.

---

## 10. File map
| Path | What it is |
|---|---|
| `mirror/ontology.py` | Typed person-ontology + `CUSTOM_EXTRACTION_INSTRUCTIONS` + edge-type map. |
| `mirror/providers.py` | Provider factory (LLM/embedder/reranker by `.env`) + prices/cost. |
| `mirror/prototype.py` | Stage-1 extraction harness: load → ingest (ensemble + fallback) → dedup → dump. |
| `mirror/transcribe.py` | Handwriting photo → proofread-ready transcript (Gemini vision). |
| `.scratch/living-memory/map.md` | Wayfinder map — canonical locked decisions + ticket index. |
| `.scratch/living-memory/issues/*.md` | One ticket per decision/question (01–10). |
| `.scratch/living-memory/assets/*.md` | Standalone research notes (bi-temporal DBs, provider landscape). |
| `BUILDLOG.md` | Build-in-public thread drafts (unposted). |
| `public/` | **git-ignored** build-in-public post drafts (local only). |
| `data/` | **git-ignored** journal entries, transcripts, graph dumps — NEVER committed. |

---

## 11. Security & privacy constraints (hard rules)
- **Journal entries and transcripts (`data/`) never leave the machine and are never committed** —
  this is a standing, non-negotiable constraint. `.gitignore` enforces it (`data/`, `*.db`, dumps).
- **Raw voice never leaves the machine** — audio transcription is planned as local faster-whisper.
- **Secrets** (`*.key`, `.env`) are git-ignored; only `.env.example` is tracked. Rotate any key that
  ever appears in a chat/commit.
- `public/` (post drafts) is local-only so nothing personal is published by accident.

---

## 12. Open threads / what's next
1. **Live-validate** the walking skeleton: `docker up` + key → `uvicorn mirror.web.app:app` → Sync →
   ask the target question in the browser (the Phase-4 checkpoint). Confirms the real Cypher + LLM.
2. **Feed more year-one entries** so "most in year one" isn't degenerate (one 2024 entry today;
   plus an untranscribed `data/entries/2026-05-19.jpeg`).
3. **Harden**: attach triggers + `ShiftedTo` targets into the answer; tune Graphiti ingest-dedup;
   design how the correction signal (`data/corrections.jsonl`) feeds back into resolution.
4. **Then v2 surfaces**: photo→transcribe→proofread-gate UI; the "proofread the graph before SAVE"
   idea; audio ingest (local faster-whisper).
5. Deferred: semantic node-dedup tuning; reflection engine (phase-two).

---

## 13. Suggested skills for the next session
- `/grilling` (or `grill-me`) — continue pressure-testing MVP scope, one thread at a time.
- `/domain-modeling` + `/codebase-design` — when designing `EntryStore`/`MemoryEngine` interfaces.
- `/prototype` — hardening the extraction module.
- `/tdd` — write the behavior-locking tests each deep-module boundary needs.
- `/buildlog` — draft a post after a shippable milestone.

---

## 14. Canonical sources (read these for the authoritative current state)
- **Map:** `.scratch/living-memory/map.md` (destination, locked constraints, decisions index).
- **Tickets:** `.scratch/living-memory/issues/01…10` — each decision with its full reasoning.
- **Research assets:** `.scratch/living-memory/assets/` — bi-temporal DB landscape, provider landscape.
- **Answer-UX mockup:** linked from ticket 09 in the map.
