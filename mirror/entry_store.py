"""EntryStore — the source of truth for proofread journal entries.

This is the sacred layer (wayfinder ticket 08): the proofread `{date, text}` entries live here,
and the knowledge graph is a *derived, rebuildable cache* of them. Everything the rest of the
system knows ultimately traces back to an Entry in this store.

Deep-module boundary (ticket 10): the public surface is small — `list / get / put / content_hash /
entries_from` — and it hides where/how entries are persisted (today: one markdown file per date
under `data/transcripts/`). Nothing here imports Graphiti, an LLM, or the graph; it is trivially
testable, and it is the one place that defines an entry's **identity**.

Identity rules (settled in the MVP grill):
  * An entry's IDENTITY is its authored **date** — one entry per date. Exact, deterministic,
    never fuzzy: two different days are two different entries even if their text is nearly
    identical (fuzzy matching belongs at the concept/node level, never here).
  * An entry's VERSION is the `content_hash` of its proofread text. A changed hash = an edit,
    which the derive layer (Phase 1) turns into a re-derive-forward. The hash is normalized so
    trivial whitespace / line-ending churn is not mistaken for a real edit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

# One entry per file, named by its authored date: 2024-01-06.md
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DEFAULT_ROOT = Path("data/transcripts")


def _normalize(text: str) -> str:
    """Canonical form for hashing/storage: strip outer whitespace, unify line endings, and drop
    trailing spaces per line — so cosmetic churn never reads as a content change (which would
    otherwise trigger a needless, costly re-derive)."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def content_hash(text: str) -> str:
    """Deterministic version id for a piece of proofread text. Same meaningful content → same
    hash, regardless of whitespace/line-ending differences."""
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Entry:
    """One proofread journal entry. `date` is identity; `content_hash` is version; `source_name`
    is the filename, kept so answers can cite the exact source (the citation guarantee)."""
    date: _date
    text: str
    content_hash: str
    source_name: str


class EntryStore:
    """A directory of proofread entries, one markdown file per authored date.

    Defaults to `data/transcripts/` (where proofread transcripts already land), but takes any root
    so tests can point at a temp dir. Reads are oldest-first, which is the order the derive layer
    must ingest in for bi-temporal `ShiftedTo` transitions to form the right way round.
    """

    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)

    # -- reads -------------------------------------------------------------
    def _entry_from_path(self, path: Path) -> Entry | None:
        m = _DATE_RE.search(path.name)
        if not m:
            return None  # not a dated entry file — skip silently (a store shouldn't chatter)
        text = path.read_text(encoding="utf-8")
        return Entry(
            date=_date(int(m[1]), int(m[2]), int(m[3])),
            text=text.strip(),
            content_hash=content_hash(text),
            source_name=path.name,
        )

    def list(self) -> list[Entry]:
        """Every entry, OLDEST FIRST. Files without a YYYY-MM-DD name are ignored."""
        if not self.root.exists():
            return []
        entries = [e for p in self.root.glob("*.md") if (e := self._entry_from_path(p))]
        return sorted(entries, key=lambda e: e.date)

    def get(self, date: _date) -> Entry | None:
        """The entry authored on `date`, or None."""
        path = self.root / f"{date.isoformat()}.md"
        return self._entry_from_path(path) if path.exists() else None

    def entries_from(self, date: _date) -> list[Entry]:
        """Entries authored on or after `date`, oldest-first — the slice a re-derive-forward
        must re-ingest after an edit to the entry dated `date`."""
        return [e for e in self.list() if e.date >= date]

    # -- writes ------------------------------------------------------------
    def put(self, date: _date, text: str) -> Entry:
        """Create or replace the proofread entry for `date`; returns the stored Entry. Text is
        normalized on the way in so identity/version stay stable. (This is the seam a future
        typed-entry or edit flow writes through; an edit that changes the text changes the
        content_hash, which the derive layer detects.)"""
        self.root.mkdir(parents=True, exist_ok=True)
        normalized = _normalize(text)
        path = self.root / f"{date.isoformat()}.md"
        path.write_text(normalized, encoding="utf-8")
        return Entry(
            date=date,
            text=normalized,
            content_hash=content_hash(normalized),
            source_name=path.name,
        )
