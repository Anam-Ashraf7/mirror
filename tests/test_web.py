"""Route tests for the web layer against a FAKE MemoryEngine — no graph, no LLM, no cost.
Proves the boundary: the web layer only calls engine.ask()/ingest() and serializes the result.

Run: python -m pytest tests/test_web.py -q
"""

from datetime import date

from fastapi.testclient import TestClient

import mirror.web.app as webapp
from mirror.web.app import create_app
from mirror.engine import AskResult, Citation
from mirror.extraction import SyncReport
from mirror.theme_resolver import ThemeResolver, Mention
from mirror.primitives import build_struggle_answer, render_answer


class FakeEngine:
    def __init__(self, result, report=None):
        self._result, self._report = result, report

    async def ask(self, question):
        return self._result

    async def ingest(self):
        return self._report


def _sample_result() -> AskResult:
    themes = ThemeResolver().resolve([
        Mention("holding anger and annoyance", "Struggle", date(2024, 1, 6),
                valid_at=date(2024, 1, 6), invalid_at=date(2025, 1, 3)),
        Mention("anger", "EmotionalState", date(2024, 1, 6),
                valid_at=date(2024, 1, 6), invalid_at=date(2025, 1, 3)),
    ])
    ans = build_struggle_answer("q", themes)
    return AskResult(answer=ans, narrative=render_answer(ans),
                     citations=[Citation(date(2024, 1, 6), "2024-01-06.md")])


def test_index_serves_the_page():
    client = TestClient(create_app(engine=FakeEngine(_sample_result())))
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>mirror</title>" in r.text


def test_ask_route_returns_grounded_cited_json():
    client = TestClient(create_app(engine=FakeEngine(_sample_result())))
    r = client.post("/api/ask", json={"question": "what did I struggle with most?"})
    d = r.json()
    assert d["found"] is True
    assert d["top_label"] == "anger"
    assert "anger" in d["narrative"]
    assert d["citations"][0]["date"] == "2024-01-06"
    assert d["citations"][0]["source"] == "2024-01-06.md"
    assert d["themes"] and "members" in d["themes"][0]        # transparency panel data present


def test_ingest_route_serializes_report():
    report = SyncReport(rederived_from=date(2024, 1, 6), ingested=[date(2024, 1, 6)],
                        removed=[], skipped=0, used_model="gpt-5.4-nano")
    client = TestClient(create_app(engine=FakeEngine(_sample_result(), report)))
    d = client.post("/api/ingest").json()
    assert d["ingested"] == ["2024-01-06"]
    assert d["used_model"] == "gpt-5.4-nano"


def test_correction_route_persists_note(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "_CORRECTIONS", tmp_path / "corr.jsonl")
    client = TestClient(create_app(engine=FakeEngine(_sample_result())))
    r = client.post("/api/correction", json={"question": "q", "note": "annoyance != anger"})
    assert r.json()["ok"] is True
    assert (tmp_path / "corr.jsonl").exists()
    assert "annoyance != anger" in (tmp_path / "corr.jsonl").read_text(encoding="utf-8")
