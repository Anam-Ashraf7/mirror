# Interaction surface: how do you actually use it?

Type: grilling
Status: resolved
Blocked by: —

## Question

What is the interface for the core engine, given it's single-user and local-first now but must
grow into something others can use later?

Candidates:
- **CLI + local scripts** — fastest to build, weakest for the photo-capture + proofread-gate flow
  and for reading longitudinal answers with citations.
- **Local web app** (Python API + simple frontend) — best fit for photo upload, the proofread
  gate, audio recording, and a readable answer view; also the natural seed for the future
  multi-user product.
- **Chat-style interface** — most natural for asking longitudinal questions, but needs a home.

Decide the day-one surface. This shapes the capture UX, the proofread gate, and the longitudinal
answer/citation display — so several downstream tickets depend on it.

## Answer

**Local web app** (Python backend/API + simple browser frontend on `localhost`), single-user. The
two most important flows — the proofread gate (compare transcript to the photo, fix, confirm) and
the longitudinal answer with click-through citations — are fundamentally visual and only a web UI
does them justice. It's also the exact seed of the future multi-user product: add auth + swap the
storage adapter, no rewrite. The chat interface lives *inside* it as the "ask a question" surface;
a CLI remains for admin/batch tasks, not as the primary face.
