"""extraction / derive — keep the knowledge graph in sync with the EntryStore.

The EntryStore is the source of truth; this module DERIVES the graph from it (wayfinder tickets
08 + 10). It owns Graphiti and is the only place entries turn into typed facts. Properties:

  * **no-wipe / incremental** — the graph accumulates across runs; re-running is idempotent.
  * **exact idempotency** — an entry already reflected at its current `content_hash` is skipped.
  * **re-derive-forward** — editing (or backfilling) an entry re-derives THAT entry and every
    entry after it, oldest-first, because the graph is a function of all entries in order (a lone
    re-add would recreate a fact fresh + un-invalidated and silently undo a real then→now shift).

The re-derive decision is a **pure function** (`plan_sync`) so it can be locked by tests with no
graph, no LLM, no cost. `GraphDeriver` is the thin I/O shell that executes a plan against Graphiti,
reusing the proven ensemble-ingest + edge-dedup from the prototype.

Each entry is stored as Graphiti Episodic node(s) named `journal-<date>-<hash12>[-p<k>]`, so the
graph is self-describing: we read back which (date, version) pairs are ingested straight from the
episode names — no external manifest to drift out of sync with the graph.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timezone

from mirror.entry_store import Entry, EntryStore

# ---------------------------------------------------------------------------
# Episode naming — the graph's self-description of what's ingested
# ---------------------------------------------------------------------------

_HASH_LEN = 12
_EPISODE_RE = re.compile(
    r"^journal-(\d{4}-\d{2}-\d{2})-([0-9a-f]{%d})(?:-p\d+)?$" % _HASH_LEN
)


def _short(content_hash: str) -> str:
    return content_hash[:_HASH_LEN]


def episode_name(date: _date, content_hash: str, pass_i: int, passes: int) -> str:
    base = f"journal-{date.isoformat()}-{_short(content_hash)}"
    return f"{base}-p{pass_i + 1}" if passes > 1 else base


def parse_episode_name(name: str) -> tuple[_date, str] | None:
    """`journal-2024-01-06-ab12cd34ef56[-p2]` -> (date(2024,1,6), 'ab12cd34ef56'), else None."""
    m = _EPISODE_RE.match(name)
    if not m:
        return None
    return _date.fromisoformat(m[1]), m[2]


# ---------------------------------------------------------------------------
# The re-derive-forward decision — PURE, fully unit-tested
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SyncPlan:
    """What to change to bring the graph in line with the store.

    rederive_from : earliest date needing work (None => graph already current, a no-op).
    ingest        : dates to (re-)ingest, oldest-first — every desired entry at/after rederive_from.
    remove        : dates whose existing episodes must be deleted first (edited/backfilled/orphaned
                    entries at/after rederive_from; a brand-new tail entry removes nothing).
    """
    rederive_from: _date | None
    ingest: list[_date] = field(default_factory=list)
    remove: list[_date] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return self.rederive_from is None


def plan_sync(
    desired: list[tuple[_date, str]],
    existing: dict[_date, set[str]],
) -> SyncPlan:
    """Given the store's desired (date, short-hash) list OLDEST-FIRST and the graph's existing
    {date: {short-hash, ...}}, decide the minimal correct re-derive-forward.

    The rule: find the EARLIEST date that's wrong — either a desired entry whose version isn't in
    the graph (new / edited / backfilled), or a date present in the graph but no longer in the
    store (deleted). That's the dirty point. Everything from there forward gets re-derived (later
    entries' bi-temporal links were computed against the old state, so they must be redone);
    everything before it is correct and left untouched (cheap). Existing episodes at/after the
    dirty point are removed first, which also cleans up edited-away old versions and orphans.
    """
    desired_dates = {d for d, _ in desired}
    dirty: list[_date] = [d for d, h in desired if h not in existing.get(d, set())]
    dirty += [d for d in existing if d not in desired_dates]   # deleted-from-store orphans
    dirty_from = min(dirty) if dirty else None

    if dirty_from is None:
        return SyncPlan(rederive_from=None)

    ingest = [d for d, _ in desired if d >= dirty_from]
    remove = sorted(d for d in existing if d >= dirty_from)
    return SyncPlan(rederive_from=dirty_from, ingest=ingest, remove=remove)


# ---------------------------------------------------------------------------
# Transient-error handling (moved from the prototype, unchanged in spirit)
# ---------------------------------------------------------------------------

TRANSIENT = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL",
             "overloaded", "Connection error")
TRANSIENT_TYPES = {
    "ReadError", "WriteError", "ConnectError", "ReadTimeout", "ConnectTimeout",
    "PoolTimeout", "RemoteProtocolError", "ServerError", "ConnectionError", "TimeoutError",
    "APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError",
}


def is_transient(err: BaseException) -> bool:
    """Walk the exception chain — Graphiti buries the real cause (a 503 or a network drop) inside
    a bare Exception, so check both text and type."""
    seen, cur = set(), err
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__ in TRANSIENT_TYPES:
            return True
        if any(k in str(cur) for k in TRANSIENT):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


# ---------------------------------------------------------------------------
# GraphDeriver — the thin I/O shell that executes a SyncPlan against Graphiti
# ---------------------------------------------------------------------------

@dataclass
class SyncReport:
    rederived_from: _date | None
    ingested: list[_date]
    removed: list[_date]
    skipped: int          # desired entries already current
    used_model: str | None


class GraphDeriver:
    """Executes plan_sync() against a live Graphiti instance. Reuses the proven ensemble ingest +
    edge-dedup. Owns Graphiti; the rest of the app never touches it directly."""

    def __init__(self, graphiti, chain: list[str], passes: int = 1, subject: str | None = None):
        self.graphiti = graphiti
        self.chain = chain
        self.passes = max(1, passes)
        self.subject = subject or os.getenv("MIRROR_SUBJECT_NAME", "Anam")
        self._idx = 0   # current position in the model fallback chain

    # -- graph introspection ----------------------------------------------
    async def existing(self) -> tuple[dict[_date, set[str]], dict[_date, list[str]]]:
        """Read back what's ingested from the episode names. Returns
        ({date: {short_hash}}, {date: [episode_uuid]}) — the first for planning, the second for
        removal."""
        records, _, _ = await self.graphiti.driver.execute_query(
            "MATCH (e:Episodic) WHERE e.name STARTS WITH 'journal-' "
            "RETURN e.name AS name, e.uuid AS uuid"
        )
        versions: dict[_date, set[str]] = {}
        uuids: dict[_date, list[str]] = {}
        for r in records or []:
            parsed = parse_episode_name(r["name"])
            if not parsed:
                continue
            d, h = parsed
            versions.setdefault(d, set()).add(h)
            uuids.setdefault(d, []).append(r["uuid"])
        return versions, uuids

    # -- the top-level operation ------------------------------------------
    async def sync(self, store: EntryStore) -> SyncReport:
        """Bring the graph in line with the store. Idempotent; re-derive-forward on edits."""
        desired_entries = store.list()  # oldest-first
        desired = [(e.date, _short(e.content_hash)) for e in desired_entries]
        versions, uuids = await self.existing()

        plan = plan_sync(desired, versions)
        if plan.is_noop:
            return SyncReport(None, [], [], skipped=len(desired), used_model=None)

        # 1) remove stale/edited episodes at/after the dirty point (so re-ingest is clean)
        for d in plan.remove:
            for uuid in uuids.get(d, []):
                await self.graphiti.remove_episode(uuid)

        # 2) re-ingest the tail, oldest-first
        by_date = {e.date: e for e in desired_entries}
        for d in plan.ingest:
            await self._ingest_entry(by_date[d])

        # 3) collapse the ensemble's duplicate edges (only meaningful for passes > 1)
        if self.passes > 1:
            await self._dedupe_edges()

        skipped = len(desired) - len(plan.ingest)
        return SyncReport(plan.rederive_from, plan.ingest, plan.remove,
                          skipped=skipped, used_model=self.chain[self._idx])

    # -- one entry, ensemble + model-fallback ------------------------------
    async def _ingest_entry(self, entry: Entry) -> None:
        from graphiti_core.nodes import EpisodeType
        from mirror.ontology import (
            ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP, CUSTOM_EXTRACTION_INSTRUCTIONS,
        )
        from mirror import providers

        framed = (f"[Journal entry written by {self.subject}. Throughout, 'I', 'me', and 'my' "
                  f"refer to {self.subject}.]\n\n{entry.text}")
        ref_time = datetime(entry.date.year, entry.date.month, entry.date.day, tzinfo=timezone.utc)

        for k in range(self.passes):
            name = episode_name(entry.date, entry.content_hash, k, self.passes)
            backoff = 0
            while True:
                try:
                    await self.graphiti.add_episode(
                        name=name,
                        episode_body=framed,
                        source=EpisodeType.text,
                        source_description="proofread journal entry",
                        reference_time=ref_time,
                        entity_types=ENTITY_TYPES,
                        edge_types=EDGE_TYPES,
                        edge_type_map=EDGE_TYPE_MAP,
                        custom_extraction_instructions=CUSTOM_EXTRACTION_INSTRUCTIONS,
                    )
                    break
                except Exception as e:  # noqa: BLE001 — non-transient re-raises
                    if not is_transient(e):
                        raise
                    if self._idx < len(self.chain) - 1:      # switch model in place, no wait
                        self._idx += 1
                        self.graphiti.llm_client = providers.make_llm_client(self.chain[self._idx])
                        continue
                    backoff += 1
                    if backoff > 4:
                        raise
                    await asyncio.sleep(min(5 * 2 ** (backoff - 1), 60))

    async def _dedupe_edges(self) -> None:
        """Collapse duplicate RELATES_TO edges left by the ensemble union, preferring to keep a
        bi-temporally-invalidated edge so then→now windows survive."""
        driver = self.graphiti.driver
        counted, _, _ = await driver.execute_query(
            "MATCH (a:Entity)-[e:RELATES_TO]->(b:Entity) "
            "WITH a, b, e.name AS rel, collect(e) AS es WHERE size(es) > 1 "
            "RETURN sum(size(es) - 1) AS removed"
        )
        removed = (counted[0].get("removed") if counted else 0) or 0
        if removed:
            await driver.execute_query(
                "MATCH (a:Entity)-[e:RELATES_TO]->(b:Entity) "
                "WITH a, b, e.name AS rel, e ORDER BY e.invalid_at DESC "
                "WITH a, b, rel, collect(e) AS es WHERE size(es) > 1 "
                "UNWIND es[1..] AS dup DELETE dup"
            )
