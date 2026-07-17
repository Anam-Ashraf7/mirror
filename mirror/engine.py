"""MemoryEngine — the one object the app talks to (wayfinder tickets 05 + 10).

It's the facade over the whole engine: `ingest()` brings the graph in line with the EntryStore
(source of truth), `ask()` answers a longitudinal question, grounded and cited. Everything below it
— Graphiti, FalkorDB, the LLM — is hidden here; the web layer never imports them. The hard thinking
(theme resolution, ranking, transitions, rendering) lives in pure, tested modules
(`theme_resolver`, `primitives`); this file is the thin shell that talks to the graph and,
optionally, lets the LLM rephrase the already-grounded answer.

Graph/LLM I/O here is validated on a live `docker up` + key run, not in the unit suite (which would
cost money and need a real graph). The correctness that matters — the re-derive-forward plan and the
answer logic — is locked purely upstream.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as _date, datetime

from mirror.entry_store import EntryStore
from mirror.extraction import GraphDeriver, SyncReport
from mirror.theme_resolver import Mention, ThemeResolver
from mirror.primitives import Answer, build_struggle_answer, render_answer

# The struggle question pulls both the persistent struggles AND the momentary feelings, because a
# theme (e.g. "anger") legitimately spans both node types (ticket 08 scatter finding).
_STRUGGLE_EDGES = ["StrugglesWith", "Experiences"]


@dataclass(frozen=True)
class Citation:
    date: _date
    source_name: str | None       # the entry file, for the "show me the source" layer


@dataclass(frozen=True)
class AskResult:
    """What the web layer renders: the grounded Answer, a plain-language narrative, and the source
    entries behind it (ticket 09's three layers: narrative → structure → cited sources)."""
    answer: Answer
    narrative: str
    citations: list[Citation] = field(default_factory=list)


def _as_date(value) -> _date | None:
    """Coerce whatever the driver returns for valid_at/invalid_at (datetime, ISO string, or None)
    into a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, _date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:19]).date()
    except ValueError:
        return None


class MemoryEngine:
    def __init__(self, graphiti, store: EntryStore, deriver: GraphDeriver):
        self.graphiti = graphiti
        self.store = store
        self.deriver = deriver

    # -- construction ------------------------------------------------------
    @classmethod
    def build(cls, store: EntryStore | None = None, passes: int | None = None) -> "MemoryEngine":
        """Wire the engine from `.env` (provider, models, ensemble passes). Mirrors the prototype's
        setup but returns the facade instead of a script."""
        os.environ.setdefault("SEMAPHORE_LIMIT", "2")   # gentle: new paid accounts are rate-limited
        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from mirror import providers

        store = store or EntryStore()
        passes = passes if passes is not None else max(1, int(os.getenv("MIRROR_ENSEMBLE_PASSES", "1")))
        chain = providers.model_chain()

        driver = FalkorDriver(
            host=os.getenv("FALKORDB_HOST", "localhost"),
            port=int(os.getenv("FALKORDB_PORT", "6379")),
            database=os.getenv("FALKORDB_DATABASE", "mirror"),
        )
        graphiti = Graphiti(
            graph_driver=driver,
            llm_client=providers.make_llm_client(chain[0]),
            embedder=providers.make_embedder(),
            cross_encoder=providers.make_reranker(),
        )
        return cls(graphiti, store, GraphDeriver(graphiti, chain, passes))

    async def setup(self) -> None:
        await self.graphiti.build_indices_and_constraints()

    async def close(self) -> None:
        await self.graphiti.close()

    # -- ingest ------------------------------------------------------------
    async def ingest(self) -> SyncReport:
        """Bring the graph in line with the store — idempotent, re-derive-forward. No wipe."""
        return await self.deriver.sync(self.store)

    # -- ask ---------------------------------------------------------------
    async def ask(self, question: str) -> AskResult:
        mentions = await self._struggle_mentions()
        themes = ThemeResolver().resolve(mentions)
        answer = build_struggle_answer(question, themes)
        narrative = await self._narrate(answer)
        citations = [
            Citation(d, self.store.get(d).source_name if self.store.get(d) else None)
            for d in answer.citations
        ]
        return AskResult(answer=answer, narrative=narrative, citations=citations)

    async def _struggle_mentions(self) -> list[Mention]:
        """Flatten the graph's struggle/feeling edges into plain Mentions for the resolver. Uses
        the edge's `valid_at` (which we stamp with the entry's authored date) as the entry date."""
        records, _, _ = await self.graphiti.driver.execute_query(
            "MATCH (a:Entity)-[e:RELATES_TO]->(n:Entity) "
            "WHERE e.name IN $edges "
            "RETURN n.name AS node, labels(n) AS labels, "
            "e.valid_at AS valid_at, e.invalid_at AS invalid_at",
            edges=_STRUGGLE_EDGES,
        )
        mentions: list[Mention] = []
        for r in records or []:
            valid = _as_date(r.get("valid_at"))
            if valid is None:
                continue   # no date → can't place it in the timeline; skip rather than guess
            node_type = next((l for l in (r.get("labels") or []) if l != "Entity"), "Entity")
            mentions.append(Mention(
                node=r["node"], node_type=node_type, entry_date=valid,
                valid_at=valid, invalid_at=_as_date(r.get("invalid_at")),
            ))
        return mentions

    async def _narrate(self, answer: Answer) -> str:
        """Deterministic grounded prose by default. If MIRROR_LLM_NARRATE=1, let the LLM REPHRASE
        that grounded text (never add facts). Falls back to the deterministic text on any error, so
        a narration hiccup never blocks a grounded, cited answer."""
        grounded = render_answer(answer)
        if os.getenv("MIRROR_LLM_NARRATE", "0") != "1":
            return grounded
        try:
            from mirror import providers
            client = providers.make_llm_client(self.deriver.chain[0])
            prompt = (
                "Rephrase the following answer in warm, plain language for the person it's about. "
                "Do NOT add, infer, or embellish any facts, names, dates, or numbers — only what is "
                "written. Keep every citation.\n\n" + grounded
            )
            from graphiti_core.prompts.models import Message
            out = await client.generate_response([Message(role="user", content=prompt)])
            text = out.get("content") if isinstance(out, dict) else str(out)
            return text or grounded
        except Exception:  # noqa: BLE001 — narration is a nicety; never break the grounded answer
            return grounded
