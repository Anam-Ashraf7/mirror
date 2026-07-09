# Reflection engine: day-one or phase-two?

Type: grilling
Status: resolved
Blocked by: —

## Question

The reflection engine is the background pass that *proactively* scans the graph, hypothesizes
non-obvious connections ("self-judgment spikes tend to follow visits with your father"), and
surfaces them into the **Inferred** layer for confirmation. It's the difference between a
database and a *living* memory.

The Observed/Inferred split is already locked as day-one architecture. This ticket decides only
the **timing of the engine itself**:
- **Phase-two (recommended):** build capture + graph + query primitives first; turn on proactive
  reflection once there's a substantial graph to find patterns in (it finds nothing on 5 entries).
- **Day-one:** build a minimal version early for the emotional "wow", accepting it stays quiet
  until the graph fills.

This gates *MVP scope & sequencing*.

## Answer

**Phase-two.** The Observed/Inferred split is built day-one (cheap now, painful to retrofit), but
the proactive reflection engine turns on only after the graph holds enough history to find real
patterns in — running it on a handful of entries surfaces noise, not insight. Build order:
capture → graph → query primitives (get trustworthy data flowing) first; switch on reflection
once there's a substantial self to reflect on. The motivational "wow-early" counter-argument was
considered and set aside in favour of a trustworthy foundation first.
