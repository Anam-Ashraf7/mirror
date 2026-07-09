# Findings: Entity resolution & cross-year extraction consistency

Research asset for ticket [06-entity-resolution-consistency](../issues/06-entity-resolution-consistency.md).

## Good news: Graphiti handles most of this natively

**Node dedup is automatic.** Graphiti runs a two-stage pipeline — `extract_nodes` / `extract_edges`
then `resolve_extracted_nodes` / `resolve_extracted_edges`. Resolution finds candidate matches
(embedding similarity + LLM judgement), and merges duplicates by creating `SAME_AS` edges into
**connected components** — one component = one resolved entity. So "impatience" written across 50
entries should collapse to a single node, with all its edges combined. This is exactly what our
longitudinal queries need.

**Contradiction handling is bi-temporal and automatic.** When a new entry contradicts an existing
fact, Graphiti *invalidates* the old edge (sets `invalid_at`) rather than deleting it, keeping
both valid-time (true-in-the-world) and transaction-time (when recorded). This is the machinery
that powers our `SHIFTED_TO` / "then vs now" for free — the old struggle stays in history, marked
as no longer current.

**Custom types are first-class.** Entity/edge types are Pydantic models; each extracted entity is
validated against its model and its attributes populated from the text.

## The real risks (hand these to the prototype, ticket 07)

1. **Over- vs under-merging.** Should "impatience" and "restlessness" be one node or two? Graphiti's
   dedup makes a call we may disagree with. Probe: inspect whether near-synonyms merged correctly.
2. **Typed-extraction drift.** The same concept might get tagged `Struggle` in one entry and
   `EmotionalState` in another, splitting a trend across two types. Probe: is tagging stable across
   entries written years apart?
3. **Premature invalidation.** Contradiction detection could mark a struggle "ended" too eagerly
   from one optimistic entry. Probe: do `SHIFTED_TO` transitions fire only on real shifts?

## Mitigations (bake into the build)

- **Capable model — already locked.** Gemini 2.5 Pro is in Graphiti's "reliable structured output"
  tier; dedup/extraction quality depends directly on this. Use `structured_output_mode="json_schema"`
  (default, constrained decoding).
- **Atomic attributes.** Break fields into smallest meaningful units; add Pydantic validators.
- **Avoid protected attribute names** on custom types: `uuid`, `name`, `group_id`, `labels`,
  `created_at`, `summary`, `attributes`, `name_embedding` are reserved by Graphiti's `EntityNode`.
- **Clear, discriminating type descriptions** in the Pydantic docstrings reduce drift between
  ambiguous types (esp. `Struggle` vs `EmotionalState`).
- **Human review remains the backstop** — the proofread gate is *before* extraction, so it can't
  catch bad tagging. The prototype (07) is where we visually verify the *graph*, and a lightweight
  "graph review" affordance may be worth adding post-MVP.

## Sources
- [getzep/graphiti | DeepWiki](https://deepwiki.com/getzep/graphiti)
- [Custom Entity and Edge Types | Zep Documentation](https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types)
- [Graphiti: Knowledge Graph Memory | Neo4j Blog](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
