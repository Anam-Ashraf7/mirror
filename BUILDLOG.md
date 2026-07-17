# Build log

Drafts of build-in-public posts about making **mirror**. Nothing here is posted automatically —
these are drafts I copy out, edit, and post myself. Nothing here is my actual journal, only the
story of building the tool.

## 2026-07-16 — why i'm building mirror, and the typo that could've broken it
<!-- source: 2aee6d7..5fe2256 + grilling session (uncommitted decisions) -->

1/ i've been journaling through 3 years of meditation and can't actually read it back — too close to see my own patterns. so i'm building mirror: a memory of myself over time. the hard part isn't the AI. it's making it never make up a nice story.

2/ i needed it to answer "then vs now", so it has to track how things change over time — a bi-temporal knowledge graph. spent a while hunting for a database that does that natively. turns out almost none do. went with Graphiti on top of FalkorDB instead.

3/ the extraction part surprised me. cheap model vs one 4x pricier — neither won. one caught feelings, the other caught insights. the real enemy was randomness: same entry, run twice, two different answers. fix: run the cheap one a few times and merge. cents per entry.

4/ the moment it clicked: it caught me angry at someone in a 2024 entry, then a year later noticing i wasn't angry anymore — and marked that as a real change over time. that's the exact thing i built this for. felt good to see it actually work.

5/ today i went to design "edit an entry" and hit a trap. fixing a typo in an old entry could silently delete one of those change-over-time links — because the graph isn't a bag of entries, it's a function of all of them, in order.

6/ so the decision: my proofread entries are the source of truth, the graph is just a cache i can rebuild. editing an old entry re-derives everything after it. costs cents, keeps the timeline honest. next up: the actual app.

---
