# Extraction-quality prototype on real entries

Type: prototype
Status: open
Blocked by: —

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
