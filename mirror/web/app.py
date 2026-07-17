"""FastAPI app for mirror's local web UI.

The web layer is a thin deep-module boundary (ticket 10): it talks ONLY to `MemoryEngine` and knows
nothing of Graphiti/FalkorDB/the LLM. It serves one page and three JSON routes:
  GET  /               → the ask page
  POST /api/ask        → answer a longitudinal question (grounded + cited)
  POST /api/ingest     → sync the graph from the EntryStore
  POST /api/correction → capture a user correction (the transparency/correction loop, ticket 08)

`create_app(engine=...)` takes an engine for tests; in production it lazily builds the real one on
first use, so importing this module (e.g. `uvicorn mirror.web.app:app`) never needs a live graph.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from mirror.engine import AskResult
from mirror.primitives import Answer
from mirror.theme_resolver import Theme

_INDEX = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
_CORRECTIONS = Path(os.getenv("MIRROR_CORRECTIONS_PATH", "data/corrections.jsonl"))


class AskBody(BaseModel):
    question: str


class CorrectionBody(BaseModel):
    question: str = ""
    note: str


def _theme_dict(t: Theme) -> dict:
    return {
        "label": t.label,
        "members": list(t.members),
        "types": sorted(t.types),
        "per_year": t.per_year,
        "total_entries": t.total_entries,
        "entry_dates": [d.isoformat() for d in t.entry_dates],
        "is_active": t.is_active,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
    }


def ask_result_dict(r: AskResult) -> dict:
    a: Answer = r.answer
    return {
        "found": a.found,
        "question": a.question,
        "narrative": r.narrative,
        "top_label": a.top_label,
        "top_total_entries": a.top_total_entries,
        "per_year": [{"year": w.year, "label": w.label, "count": w.count} for w in a.per_year],
        "is_active": a.is_active,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "citations": [{"date": c.date.isoformat(), "source": c.source_name} for c in r.citations],
        "themes": [_theme_dict(t) for t in a.themes],
    }


def create_app(engine=None) -> FastAPI:
    app = FastAPI(title="mirror")
    state = {"engine": engine}

    async def get_engine():
        if state["engine"] is None:
            from mirror.engine import MemoryEngine
            eng = MemoryEngine.build()
            await eng.setup()
            state["engine"] = eng
        return state["engine"]

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _INDEX

    @app.post("/api/ask")
    async def ask(body: AskBody) -> JSONResponse:
        eng = await get_engine()
        result = await eng.ask(body.question)
        return JSONResponse(ask_result_dict(result))

    @app.post("/api/ingest")
    async def ingest() -> JSONResponse:
        eng = await get_engine()
        report = await eng.ingest()
        return JSONResponse({
            "rederived_from": report.rederived_from.isoformat() if report.rederived_from else None,
            "ingested": [d.isoformat() for d in report.ingested],
            "removed": [d.isoformat() for d in report.removed],
            "skipped": report.skipped,
            "used_model": report.used_model,
        })

    @app.post("/api/correction")
    async def correction(body: CorrectionBody) -> JSONResponse:
        # v1 stub for the correction signal (ticket 08 "still open"): append to a local JSONL so
        # nothing is lost and we can later feed it back into resolution tuning.
        _CORRECTIONS.parent.mkdir(parents=True, exist_ok=True)
        with _CORRECTIONS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "at": datetime.now(timezone.utc).isoformat(),
                "question": body.question,
                "note": body.note,
            }) + "\n")
        return JSONResponse({"ok": True})

    return app


app = create_app()   # module-level for `uvicorn mirror.web.app:app` (builds engine lazily)
