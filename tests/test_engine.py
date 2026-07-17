"""Glue tests for the MemoryEngine facade — validates the graph-row → answer flow against a FAKE
graph (canned Cypher rows), so no FalkorDB/LLM/cost is needed. The live wiring (real driver, real
model) is validated separately on a `docker up` + key run.

Run: python -m pytest tests/test_engine.py -q
"""

import asyncio
from datetime import date

from mirror.entry_store import EntryStore
from mirror.engine import MemoryEngine, _as_date


class _FakeDriver:
    def __init__(self, records):
        self._records = records

    async def execute_query(self, query, **kwargs):
        return self._records, None, None


class _FakeGraphiti:
    def __init__(self, records):
        self.driver = _FakeDriver(records)


Q = "what did I struggle with most, and where is it now?"


def test_as_date_coerces_iso_datetime_and_none():
    assert _as_date("2024-01-06T00:00:00") == date(2024, 1, 6)
    assert _as_date(None) is None


def test_ask_end_to_end_against_fake_graph(tmp_path):
    store = EntryStore(tmp_path)
    store.put(date(2024, 1, 6), "entry one")
    store.put(date(2025, 1, 3), "entry two")

    records = [
        {"node": "holding anger and annoyance", "labels": ["Entity", "Struggle"],
         "valid_at": "2024-01-06T00:00:00", "invalid_at": None},
        {"node": "Persistent anger and annoyance", "labels": ["Entity", "Struggle"],
         "valid_at": "2025-01-03T00:00:00", "invalid_at": None},
        {"node": "anger", "labels": ["Entity", "EmotionalState"],
         "valid_at": "2024-01-06T00:00:00", "invalid_at": "2025-01-03T00:00:00"},
    ]
    engine = MemoryEngine(_FakeGraphiti(records), store, deriver=None)

    result = asyncio.run(engine.ask(Q))

    assert result.answer.found is True
    assert result.answer.top_label == "anger"
    assert "anger" in result.narrative                       # grounded prose
    # citations resolve to the real entry files in the store
    assert {c.date for c in result.citations} == {date(2024, 1, 6), date(2025, 1, 3)}
    assert all(c.source_name for c in result.citations)


def test_ask_refuses_when_graph_empty(tmp_path):
    engine = MemoryEngine(_FakeGraphiti([]), EntryStore(tmp_path), deriver=None)
    result = asyncio.run(engine.ask(Q))
    assert result.answer.found is False
    assert "invent" in result.narrative.lower()              # refuse, don't fabricate
