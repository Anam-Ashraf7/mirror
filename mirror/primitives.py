"""Analytical primitives — the deterministic answer skeleton behind a longitudinal question.

v1 ships two (wayfinder ticket 08): **Ranking** ("what did I struggle with most" — by distinct
entries, per year and overall) and **Transitions** ("where is it now" — from the theme's
bi-temporal status). This module turns resolved `Theme`s into a structured, **fully-cited**
`Answer`. It is pure and deterministic: the LLM later NARRATES over this, it never decides the
facts, and no claim exists without the entries that back it (the citation guarantee, ticket 09).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date

from mirror.theme_resolver import Theme


@dataclass(frozen=True)
class YearTop:
    """The most-present struggle theme in a given year."""
    year: int
    label: str
    count: int          # distinct entries that year


@dataclass(frozen=True)
class Answer:
    """The grounded skeleton for 'what did I struggle with most, and where is it now?'.
    `themes` is the full ranked view for the transparency panel; `top_*` and `per_year` are the
    ranking; `is_active`/`resolved_at` are the transition; `citations` are the backing entries."""
    question: str
    found: bool
    top_label: str | None
    top_total_entries: int
    per_year: list[YearTop]
    is_active: bool | None
    resolved_at: _date | None
    citations: tuple[_date, ...]
    themes: list[Theme] = field(default_factory=list)


def render_answer(answer: Answer) -> str:
    """Deterministic, grounded prose from an Answer — no LLM. Every sentence traces to the
    structured facts, and it always ends in citations. The LLM (if enabled) only rephrases THIS;
    it never adds facts. Guarantees a cited answer even when no model is configured."""
    if not answer.found:
        return ("I don't see any struggles recorded in your entries yet, so I can't answer that "
                "without inventing one. Add or ingest a few entries and ask again.")

    parts = [
        f"Your most persistent struggle was “{answer.top_label}” — it appears in "
        f"{answer.top_total_entries} "
        f"{'entry' if answer.top_total_entries == 1 else 'entries'}."
    ]
    if answer.per_year:
        yr = "; ".join(f"{w.year}: {w.label} ({w.count})" for w in answer.per_year)
        parts.append(f"Year by year, the most present struggle was — {yr}.")
    if answer.is_active:
        parts.append("Where it is now: still present in your most recent entries.")
    elif answer.resolved_at is not None:
        parts.append(f"Where it is now: it appears to have shifted or eased — its last recorded "
                     f"instance was invalidated by a later entry on {answer.resolved_at.isoformat()}.")
    if answer.citations:
        cites = ", ".join(d.isoformat() for d in answer.citations)
        parts.append(f"Based on your entries from: {cites}.")
    return " ".join(parts)


def _year_winners(struggle_themes: list[Theme]) -> list[YearTop]:
    """For each year any struggle theme appears, the theme that dominated it — ties broken by
    overall size then label, so it's deterministic."""
    years = sorted({y for t in struggle_themes for y in t.per_year})
    winners: list[YearTop] = []
    for year in years:
        present = [t for t in struggle_themes if t.per_year.get(year, 0) > 0]
        best = min(present, key=lambda t: (-t.per_year[year], -t.total_entries, t.label))
        winners.append(YearTop(year=year, label=best.label, count=best.per_year[year]))
    return winners


def build_struggle_answer(question: str, themes: list[Theme]) -> Answer:
    """Ranking + Transitions for the struggle question. `themes` must already be ranked by
    `ThemeResolver` (descending distinct-entry count). Returns a graceful not-found Answer when
    there are no struggle themes (ticket 09: refuse rather than invent)."""
    struggle_themes = [t for t in themes if "Struggle" in t.types]
    if not struggle_themes:
        return Answer(
            question=question, found=False, top_label=None, top_total_entries=0,
            per_year=[], is_active=None, resolved_at=None, citations=(), themes=themes,
        )

    top = struggle_themes[0]   # already the most distinct-entries theme with a Struggle
    return Answer(
        question=question,
        found=True,
        top_label=top.label,
        top_total_entries=top.total_entries,
        per_year=_year_winners(struggle_themes),
        is_active=top.is_active,
        resolved_at=top.resolved_at,
        citations=top.entry_dates,
        themes=themes,
    )
