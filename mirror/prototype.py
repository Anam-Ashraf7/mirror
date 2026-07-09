"""Stage-1 extraction-quality prototype (wayfinder ticket 07).

Reads dated journal entries, ingests them oldest-first into a temporal knowledge
graph (Graphiti + FalkorDB, Gemini extraction/embedding), then prints what the graph
actually holds so we can judge fidelity WITH the user.

Run:
    1. docker compose up -d                 # start FalkorDB
    2. cp .env.example .env  &&  edit .env   # add GEMINI_API_KEY
    3. pip install -r requirements.txt
    4. put entries in data/entries/ named YYYY-MM-DD.md   (one entry per file)
    5. python -m mirror.prototype

Nothing here is production code — it's a throwaway harness to answer one question:
does the graph faithfully represent what the entries actually say?
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient

from mirror.ontology import ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP

# --- provider config (behind these constants is the whole "swap later" story) ---
LLM_MODEL = "gemini-2.5-pro"            # extraction brain (locked decision)
EMBED_MODEL = "embedding-001"           # Gemini embeddings (update if your key prefers another)
RERANK_MODEL = "gemini-2.5-flash-lite"  # cheap reranker, keeps us single-vendor

ENTRIES_DIR = Path("data/entries")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def load_entries() -> list[tuple[datetime, str, str]]:
    """Return (date, filename, text) for each entry, sorted OLDEST FIRST.

    Date is parsed from the filename (YYYY-MM-DD...). Oldest-first ordering is what
    lets Graphiti build `ShiftedTo` transitions in the right temporal direction.
    """
    if not ENTRIES_DIR.exists():
        raise SystemExit(
            f"\n  No entries found. Create {ENTRIES_DIR}/ and drop in files named\n"
            f"  YYYY-MM-DD.md (one journal entry each), then re-run.\n"
        )
    entries = []
    for path in ENTRIES_DIR.glob("*.md"):
        m = DATE_RE.search(path.name)
        if not m:
            print(f"  ! skipping {path.name} — no YYYY-MM-DD date in filename")
            continue
        date = datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        text = path.read_text(encoding="utf-8").strip()
        if text:
            entries.append((date, path.name, text))
    if not entries:
        raise SystemExit(f"\n  {ENTRIES_DIR}/ has no dated *.md entries yet.\n")
    return sorted(entries, key=lambda e: e[0])


def build_graphiti() -> Graphiti:
    api_key = os.environ["GEMINI_API_KEY"]
    driver = FalkorDriver(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        database=os.getenv("FALKORDB_DATABASE", "mirror"),
    )
    return Graphiti(
        graph_driver=driver,
        llm_client=GeminiClient(config=LLMConfig(api_key=api_key, model=LLM_MODEL)),
        embedder=GeminiEmbedder(config=GeminiEmbedderConfig(api_key=api_key, embedding_model=EMBED_MODEL)),
        cross_encoder=GeminiRerankerClient(config=LLMConfig(api_key=api_key, model=RERANK_MODEL)),
    )


async def ingest(graphiti: Graphiti, entries) -> None:
    for date, filename, text in entries:
        print(f"  → ingesting {filename}  ({date.date()})  [{len(text)} chars]")
        await graphiti.add_episode(
            name=f"journal-{date.date()}",
            episode_body=text,
            source=EpisodeType.text,
            source_description="handwritten journal entry (proofread)",
            reference_time=date,           # <-- the authored date, NOT today. Critical.
            entity_types=ENTITY_TYPES,
            edge_types=EDGE_TYPES,
            edge_type_map=EDGE_TYPE_MAP,
        )


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
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("  Set GEMINI_API_KEY in .env (see .env.example).")

    entries = load_entries()
    print(f"\n  Loaded {len(entries)} entries, "
          f"{entries[0][0].date()} → {entries[-1][0].date()} (oldest first).\n")

    graphiti = build_graphiti()
    try:
        await graphiti.build_indices_and_constraints()
        await ingest(graphiti, entries)
        await dump_graph(graphiti)
    finally:
        await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())
