# Entity resolution & cross-year extraction consistency

Type: research
Status: resolved
Blocked by: —

## Question

The typed ontology only answers longitudinal questions if the *same* concept is tagged the *same
way* across 3 years. Research how Graphiti handles this and where the risks are:
- **Entity resolution / dedup:** how does Graphiti merge "impatience" mentioned across 50 entries
  into one node vs spawning near-duplicates? What controls it (embeddings, LLM reconciliation)?
- **Edge invalidation:** how `SHIFTED_TO` / conflicting facts drive `valid_at` / `invalid_at`.
- **Typed-extraction drift:** how stable is Gemini's assignment of custom entity/edge types over
  many entries, and what mitigations exist (naming conventions, few-shot, canonicalization).

Produce a markdown summary of findings + concrete risks the prototype (07) should probe.

## Answer

**Mostly handled natively, with three risks to probe empirically.** Graphiti auto-dedups nodes
(embedding + LLM match → `SAME_AS` connected components, so "impatience" across 50 entries collapses
to one node) and auto-invalidates contradicted facts bi-temporally (`invalid_at`) — which powers
`SHIFTED_TO` / then-vs-now for free. Custom Pydantic types are first-class. Extraction/dedup quality
rides on the LLM's structured output — Gemini 2.5 Pro (locked) is in the reliable tier; use
`structured_output_mode="json_schema"`, atomic attributes, avoid Graphiti's protected attribute
names, and write discriminating type descriptions. **Risks for the prototype to test:** (1) over/under-
merging of near-synonyms, (2) typed-extraction drift across years, (3) premature contradiction
invalidation. Full findings + mitigations + sources:
[findings](../assets/06-entity-resolution-findings.md).
