# Findings: Is there a bi-temporal graph database like Graphiti?

Research note prompted by the question "there is a bi-temporal graph database like Graphiti — I
couldn't find it, is there?" Short answer: **native bi-temporal *graph* databases barely exist.**
The research literature is blunt — *"only few graph databases deal with both [valid and transaction]
time."* Bitemporality is standard in relational/document databases, but in graph-land it is almost
always added in a **framework layer** (like Graphiti) on top of a non-temporal graph DB — which is
exactly what mirror does with Graphiti + FalkorDB.

## The distinction that matters

Two different layers get called "bi-temporal," and conflating them is what makes this hard to find:

- **A bi-temporal *database*** — the storage engine itself tracks valid-time (true-in-the-world)
  and transaction-time (when recorded), and lets you query `AS OF` either axis.
- **A bi-temporal *framework*** (Graphiti) — a library that adds those semantics *in software* over
  a plain graph DB, *and* does the LLM extraction that turns text into the graph.

Graphiti is the second kind. It is **not a database** — it layers bi-temporal edges
(`valid_at` / `invalid_at` + transaction time) over FalkorDB/Neo4j/Kuzu.

## Native bi-temporal *databases* (engine does the time-tracking)

| System | Bi-temporal? | Graph? | Notes |
|---|---|---|---|
| **XTDB** | ✅ **native, first-class** (valid + transaction time) | document + Datalog/SQL, graph-ish — not a property graph | The one true bitemporal database. Immutable, open-source (JUXT). This is the thing being hunted for. |
| **TerminusDB** | ⚠️ partial | ✅ real document-graph DB | Git-like versioning, time-travel, diffs; v12 added Allen-interval temporal reasoning. But mostly *transaction-time* (version history), not full fact-validity bitemporal. |
| **TypeDB** | ❌ not native | ✅ typed knowledge graph + reasoning | Temporal validity is user-defined metadata; no `AT TIME` query. |
| **Datomic** | ❌ (time-travel only) | graph-ish | Immutable `as-of` history on *one* axis (transaction time); valid-time you model yourself. |
| Neo4j / FalkorDB / Memgraph / Kuzu | ❌ | ✅ | Plain graph DBs — you implement bitemporality in the model. **This is what Graphiti does for us.** |

**Bottom line:** XTDB is the only widely-used database that is bi-temporal by design — but it's a
document/SQL database, not a pure knowledge graph. A *native bitemporal graph* database effectively
does not exist yet.

## Frameworks like Graphiti (bi-temporal semantics in software)

| Framework | Local-first? | Notes |
|---|---|---|
| **Graphiti / Zep** | ✅ self-host | The leader; every edge carries `t_valid` / `t_invalid`. What mirror uses. |
| **Cognee** | ✅ fully local (SQLite + LanceDB + Kuzu) | Closest local-first alternative; graph-first, air-gapped. |
| **Hindsight** | ✅ free self-hosted | Strong benchmark scores (91.4% LongMemEval); worth watching. |
| Mem0 (graph) / Letta / Memori | mixed | Recall-oriented; weaker on true bitemporality. |

## Decision for mirror: stay on Graphiti

The key insight: **XTDB gives bi-temporal *storage* — not the *knowledge extraction*.** It would
faithfully store valid/transaction time, but we'd have to build the entire
"journal text → typed entities → time-stamped edges → dedup → invalidation" pipeline ourselves.
**Graphiti gives us both** — LLM-powered extraction *and* bitemporal semantics — which is precisely
why it was chosen.

Switching mirror to XTDB would be a **step backward**: nicer storage engine, but we'd lose all the
extraction machinery that turns handwriting into a graph. Graphiti-over-FalkorDB remains the right
call.

**Worth remembering:** if mirror ever ingests *already-structured* data (mood-tracker numbers,
calendar events) where no extraction is needed, XTDB would be a beautiful native-bitemporal home
for it. Graphiti also can't run *on* XTDB — its drivers are Neo4j/FalkorDB/Kuzu only — so the two
aren't combinable; they'd be separate stores.

## Sources
- [XTDB — bitemporality docs](https://v1-docs.xtdb.com/concepts/bitemporality/)
- [XTDB — immutable SQL database](https://xtdb.com/)
- [TerminusDB (git-for-data graph)](https://terminusdb.org/)
- [Bitemporal Property Graphs (research)](https://dl.acm.org/doi/10.1007/978-3-032-05281-0_15)
- [Zep/Graphiti vs Cognee comparison](https://vectorize.io/articles/zep-vs-cognee)
