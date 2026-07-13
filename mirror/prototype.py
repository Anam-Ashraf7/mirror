"""Stage-1 extraction-quality prototype (wayfinder ticket 07).

Reads dated journal entries, ingests them oldest-first into a temporal knowledge
graph (Graphiti + FalkorDB, Gemini extraction/embedding), then prints what the graph
actually holds so we can judge fidelity WITH the user.

Run:
    1. docker compose up -d                 # start FalkorDB
    2. cp .env.example .env  &&  edit .env   # add GEMINI_API_KEY
    3. pip install -r requirements.txt
    4. put page images in data/entries/ (YYYY-MM-DD[-N].jpeg), then:
       python -m mirror.transcribe        # images -> data/transcripts/*.md
       (proofread the transcripts against your notebook)
    5. python -m mirror.prototype         # ingest the proofread transcripts

Nothing here is production code — it's a throwaway harness to answer one question:
does the graph faithfully represent what the entries actually say?
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

try:  # force UTF-8 stdout so arrows/bullets don't crash on cp1252 consoles (Windows)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

# Keep Gemini calls gentle — one at a time — to dodge 503 "high demand" and free-tier rate
# caps. Must be set BEFORE graphiti_core is imported (it reads this at import).
os.environ.setdefault("SEMAPHORE_LIMIT", "1")

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.driver.falkordb_driver import FalkorDriver

from mirror.ontology import (
    ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP, CUSTOM_EXTRACTION_INSTRUCTIONS,
)
from mirror import providers  # provider factory: gemini | openai | anyone-openai-compatible

TRANSCRIPTS_DIR = Path("data/transcripts")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def load_entries() -> list[tuple[datetime, str, str]]:
    """Return (date, filename, text) for each proofread transcript, sorted OLDEST FIRST.

    One transcript file = one entry (multi-page images were already merged by
    `mirror.transcribe`). Date is parsed from the filename (YYYY-MM-DD.md). Oldest-first
    ordering is what lets Graphiti build `ShiftedTo` transitions in the right direction.
    """
    if not TRANSCRIPTS_DIR.exists():
        raise SystemExit(
            f"\n  No transcripts found. Run `python -m mirror.transcribe` first to turn\n"
            f"  your page images in data/entries/ into proofread-ready {TRANSCRIPTS_DIR}/*.md,\n"
            f"  proofread them, then re-run this.\n"
        )
    entries = []
    for path in TRANSCRIPTS_DIR.glob("*.md"):
        m = DATE_RE.search(path.name)
        if not m:
            print(f"  ! skipping {path.name} — no YYYY-MM-DD date in filename")
            continue
        date = datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        text = path.read_text(encoding="utf-8").strip()
        if text:
            entries.append((date, path.name, text))
    if not entries:
        raise SystemExit(f"\n  {TRANSCRIPTS_DIR}/ has no dated *.md transcripts yet.\n")
    return sorted(entries, key=lambda e: e[0])


def build_graphiti(llm_model: str) -> Graphiti:
    driver = FalkorDriver(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        database=os.getenv("FALKORDB_DATABASE", "mirror"),
    )
    prov = providers.provider_name()
    print(f"  provider={prov}  llm={llm_model}  small={providers.small_model()}  "
          f"embed={providers.embed_model()}  rerank={providers.rerank_model()}")
    return Graphiti(
        graph_driver=driver,
        llm_client=providers.make_llm_client(llm_model),
        embedder=providers.make_embedder(),
        cross_encoder=providers.make_reranker(),
    )


# There should be better way than to wipe the graph between runs, we need to find a way to somehow keep whatever was ingested in the previous run and only add new entries. But for now, this is a simple way to ensure that we don't have duplicates in the graph.
async def clear_graph(graphiti: Graphiti) -> None:
    """Wipe the graph so a mid-run model switch doesn't leave half-ingested duplicates."""
    await graphiti.driver.execute_query("MATCH (n) DETACH DELETE n")


# transient by message text (server capacity / rate) ...
TRANSIENT = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL",
             "overloaded", "Connection error")
# ... or by exception TYPE (network drops, which carry an empty message). Includes both httpx
# and OpenAI-SDK (APIConnectionError/APITimeoutError/InternalServerError) transient names.
TRANSIENT_TYPES = {
    "ReadError", "WriteError", "ConnectError", "ReadTimeout", "ConnectTimeout",
    "PoolTimeout", "RemoteProtocolError", "ServerError", "ConnectionError", "TimeoutError",
    "APIConnectionError", "APITimeoutError", "InternalServerError", "RateLimitError",
}


def _is_transient(err: BaseException) -> bool:
    """Walk the exception chain — Graphiti buries the real cause (a 503 or a network
    ReadError) inside a bare, message-less Exception, so check both text and type."""
    seen, cur = set(), err
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if type(cur).__name__ in TRANSIENT_TYPES:
            return True
        if any(k in str(cur) for k in TRANSIENT):
            return True
        cur = cur.__cause__ or cur.__context__
    return False


async def ingest(graphiti: Graphiti, entries, chain: list[str], passes: int = 1) -> str:
    """Ingest each entry, keeping completed work. On a transient 503 we SWITCH the live
    model to the next in the chain (instantly, no wipe) and retry the same call; only on the
    last model do we wait-and-retry. The model index persists across entries.

    ENSEMBLE (passes > 1): extraction on a cheap model is high-variance — a given run may
    catch emotions but miss insights, or vice-versa. So we ingest each entry `passes` times;
    Graphiti's entity resolution merges the overlap (SAME_AS components) while the UNION of
    what each pass caught survives. All passes share the entry's reference_time, so bi-temporal
    ordering is untouched. Costs ~passes× the tokens (still cents on nano)."""
    subject = os.getenv("MIRROR_SUBJECT_NAME", "Anam")
    state = {"idx": 0}

    async def _add(name: str, framed: str, date) -> None:
        backoff = 0
        while True:
            try:
                await graphiti.add_episode(
                    name=name,
                    episode_body=framed,
                    source=EpisodeType.text,
                    source_description="handwritten journal entry (proofread)",
                    reference_time=date,   # <-- the authored date, NOT today. Critical.
                    entity_types=ENTITY_TYPES,
                    edge_types=EDGE_TYPES,
                    edge_type_map=EDGE_TYPE_MAP,
                    custom_extraction_instructions=CUSTOM_EXTRACTION_INSTRUCTIONS,
                )
                return
            except Exception as e:  # noqa: BLE001 — non-transient errors re-raise below
                if not _is_transient(e):
                    raise
                if state["idx"] < len(chain) - 1:             # switch model instantly, no wait
                    state["idx"] += 1
                    graphiti.llm_client = providers.make_llm_client(chain[state["idx"]])
                    print(f"      '{chain[state['idx'] - 1]}' overloaded → switched to "
                          f"'{chain[state['idx']]}', retrying")
                    continue
                backoff += 1                                  # last model: be patient
                if backoff > 4:
                    raise
                wait = min(5 * 2 ** (backoff - 1), 60)
                print(f"      '{chain[state['idx']]}' busy — waiting {wait}s (retry {backoff}/4)")
                await asyncio.sleep(wait)

    for date, filename, text in entries:
        # Anchor the first-person author so edges attach to a real "self" node, not to
        # random concepts. Without this, "I practice meditation" has nothing to hang off.
        framed = (f"[Journal entry written by {subject}. Throughout, 'I', 'me', and 'my' "
                  f"refer to {subject}.]\n\n{text}")
        tag = f"  (ensemble x{passes})" if passes > 1 else ""
        print(f"  → ingesting {filename}  ({date.date()})  [{len(text)} chars]  "
              f"via {chain[state['idx']]}{tag}")
        for k in range(passes):
            # distinct episode name per pass; ENTITY dedup unions extractions across passes.
            name = f"journal-{date.date()}" + (f"-p{k + 1}" if passes > 1 else "")
            await _add(name, framed, date)
    return chain[state["idx"]]   # the model actually in use at the end (for cost reporting)


async def dedupe_graph(graphiti: Graphiti) -> None:
    """Post-ensemble cleanup. The multi-pass union recovers recall but leaves DUPLICATE EDGES
    — the same (source, relation, target) extracted on more than one pass — because Graphiti
    dedups nodes well but facts poorly across near-identical re-ingestions. Collapse each
    duplicate group to a single edge, preferring to keep a bi-temporally-invalidated edge over
    a plain one so 'then→now' windows survive.

    (Near-duplicate NODES with different wording — "listen to my heart" vs "I need to listen to
    my heart" — are a separate, semantic problem; deterministic string-merge is unsafe, so that
    is left for the real build's entity-resolution tuning.)"""
    driver = graphiti.driver
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
        print(f"  deduped {removed} duplicate edge(s) from the ensemble union")


async def dump_graph(graphiti: Graphiti) -> None:
    """Print what the graph now holds — the fidelity check surface."""
    driver = graphiti.driver
    print("\n" + "=" * 60 + "\n  RESULTING GRAPH\n" + "=" * 60)

    nodes, _, _ = await driver.execute_query(
        "MATCH (n:Entity) RETURN n.name AS name, labels(n) AS labels, "
        "n.summary AS summary ORDER BY name"
    )
    print(f"\n  ENTITIES ({len(nodes)}):")
    for r in nodes:
        extra = [l for l in (r.get("labels") or []) if l != "Entity"]
        tag = f"  [{', '.join(extra)}]" if extra else ""
        print(f"    • {r['name']}{tag}")
        if r.get("summary"):
            print(f"        {r['summary'][:110]}")

    edges, _, _ = await driver.execute_query(
        "MATCH (a:Entity)-[e:RELATES_TO]->(b:Entity) "
        "RETURN a.name AS src, e.name AS rel, b.name AS dst, "
        "e.fact AS fact, e.valid_at AS valid_at, e.invalid_at AS invalid_at "
        "ORDER BY valid_at"
    )
    print(f"\n  RELATIONSHIPS ({len(edges)}):")
    for r in edges:
        window = ""
        if r.get("valid_at"):
            window = f"  ({str(r['valid_at'])[:10]}"
            window += f" → {str(r['invalid_at'])[:10]})" if r.get("invalid_at") else " → …)"
        print(f"    • {r['src']} —[{r['rel']}]→ {r['dst']}{window}")
        if r.get("fact"):
            print(f"        \"{r['fact'][:110]}\"")

    print("\n  → Eyeball check: do these entities/edges match what you actually wrote?")
    print("    Watch for the ticket-06 risks: over/under-merged concepts, type drift,")
    print("    and any ShiftedTo that fired without a real shift.\n")


async def main() -> None:
    load_dotenv()
    prov = providers.provider_name()
    key = providers.api_key(prov)   # fail fast with a clear message if the key is missing
    if prov == "gemini":
        # Use OUR key unambiguously: drop any ambient GOOGLE_API_KEY so the SDK can't
        # silently pick a different account/quota.
        os.environ.pop("GOOGLE_API_KEY", None)
    else:
        # Belt-and-braces: some code paths read OPENAI_API_KEY from the environment even
        # though we pass the key explicitly. Normalize the accepted spelling.
        os.environ["OPENAI_API_KEY"] = key

    entries = load_entries()
    limit = int(os.getenv("MIRROR_MAX_ENTRIES", "0"))   # e.g. 1 to validate cheaply
    if limit > 0:
        entries = entries[:limit]
    print(f"\n  Loaded {len(entries)} entries, "
          f"{entries[0][0].date()} → {entries[-1][0].date()} (oldest first).\n")

    chain = providers.model_chain()
    passes = max(1, int(os.getenv("MIRROR_ENSEMBLE_PASSES", "1")))   # >1 = ensemble union
    graphiti = build_graphiti(chain[0])          # built once; model swaps happen in-place
    try:
        await graphiti.build_indices_and_constraints()
        print("  wiping graph for a fresh run (so re-runs don't stack duplicate entries)\n")
        await clear_graph(graphiti)
        used_model = await ingest(graphiti, entries, chain, passes)
        usage = graphiti.llm_client.token_tracker.get_total_usage()
        cost = providers.cost_for(used_model, usage.input_tokens, usage.output_tokens)
        line = (f"\n  COST  model={used_model}  reasoning={os.getenv('MIRROR_OPENAI_REASONING', '-')}"
                f"  in={usage.input_tokens:,}  out={usage.output_tokens:,}")
        if cost is not None and usage.total_tokens > 0:
            n = len(entries)
            line += f"  ≈ ${cost:.4f}/{n}entry  → ${cost / n:.4f}/entry"
        print(line)
        if passes > 1:
            await dedupe_graph(graphiti)   # collapse the ensemble's duplicate edges
        await dump_graph(graphiti)
    finally:
        await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())
