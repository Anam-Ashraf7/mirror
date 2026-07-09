# Longitudinal answer & citation UX

Type: prototype
Status: resolved
Blocked by: 03

## Question

How does a longitudinal question get asked, and how is its answer shown so the user *trusts* it?
Prototype the answer surface:
- Posing a question and routing it through the analytical primitives (Timeline / Transitions /
  Ranking / CoOccurrence) vs open graph exploration.
- Rendering the answer with **inline citations** back to the exact source entries (click-through
  to what was actually written) — the trust mechanism.
- Showing a timeline / then-vs-now view for "how have I changed" without inventing anything.

Depends on the interaction surface (03) being chosen.

## Answer

**Three-layer, narrative-first answer view, with the citation as the hero and honest refusal.**
Confirmed via clickable mockup:
- **Layer 1 — narrative** (serif prose): the LLM's *only* job is phrasing; a few sentences of synthesis.
- **Layer 2 — evidence spine**: a timeline of the actual `SHIFTED_TO` transitions (dates + coarse
  intensity), rendered straight from the deterministic primitive — not prose. Runs warm→cool.
- **Layer 3 — sources**: every claim links to the real entry that justifies it; clicking a citation
  marker highlights + scrolls to that entry. **Rule: no claim is shown without a citation.**
- **Graceful refusal + suggestions**: when the graph lacks the evidence, it says so honestly (with a
  count of what it found) and proposes adjacent questions the record *can* answer.
- **Default: narrative first**, drill down to evidence and sources.

Mockup asset: [09-answer-ux-mockup.html](../assets/09-answer-ux-mockup.html) ·
live: https://claude.ai/code/artifact/9f745aa5-4e02-473b-a072-ff8c8e01c3d1
