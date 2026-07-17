"""Behavior-locking tests for the analytical primitives (Ranking + Transitions).

Pure — builds Themes via the real ThemeResolver from Mention fixtures, then checks the Answer.
Run: python -m pytest tests/test_primitives.py -q
"""

from datetime import date

from mirror.theme_resolver import ThemeResolver, Mention
from mirror.primitives import build_struggle_answer, render_answer, Answer


D24 = date(2024, 1, 6)
D25 = date(2025, 1, 3)
Q = "what did I struggle with most, and where is it now?"


def _resolve(mentions):
    return ThemeResolver().resolve(mentions)


def test_not_found_when_no_struggles():
    themes = _resolve([Mention("joy", "EmotionalState", D24)])
    ans = build_struggle_answer(Q, themes)
    assert ans.found is False
    assert ans.top_label is None and ans.per_year == []


def test_top_struggle_and_citations():
    themes = _resolve([
        Mention("holding anger and annoyance", "Struggle", D24, valid_at=D24),
        Mention("Persistent anger and annoyance", "Struggle", D25, valid_at=D25),
        Mention("avoiding vulnerability by lying", "Struggle", D24, valid_at=D24),
    ])
    ans = build_struggle_answer(Q, themes)
    assert ans.found is True
    assert ans.top_label == "anger"                 # 2 entries beats vulnerability's 1
    assert ans.top_total_entries == 2
    assert ans.citations == (D24, D25)              # the actual entries backing it


def test_per_year_winner_can_differ_across_years():
    # 2024 dominated by anger; 2025 dominated by vulnerability
    themes = _resolve([
        Mention("holding anger", "Struggle", D24, valid_at=D24),
        Mention("anger again", "Struggle", date(2024, 6, 1), valid_at=date(2024, 6, 1)),
        Mention("avoiding vulnerability", "Struggle", D25, valid_at=D25),
    ])
    ans = build_struggle_answer(Q, themes)
    winners = {w.year: w.label for w in ans.per_year}
    assert winners[2024] == "anger"
    assert winners[2025] == "vulnerability"


def test_where_is_it_now_resolved():
    themes = _resolve([
        Mention("holding anger", "Struggle", D24, valid_at=D24, invalid_at=D25),
    ])
    ans = build_struggle_answer(Q, themes)
    assert ans.is_active is False
    assert ans.resolved_at == D25


def test_where_is_it_now_still_active():
    themes = _resolve([
        Mention("holding anger", "Struggle", D24, valid_at=D24),
        Mention("still holding anger", "Struggle", D25, valid_at=D25),
    ])
    ans = build_struggle_answer(Q, themes)
    assert ans.is_active is True
    assert ans.resolved_at is None


# -- deterministic renderer: grounded prose, always cited ----------------------

def test_render_answer_is_grounded_and_cited():
    themes = _resolve([
        Mention("holding anger", "Struggle", D24, valid_at=D24, invalid_at=D25),
    ])
    text = render_answer(build_struggle_answer(Q, themes))
    assert "anger" in text
    assert "shifted or eased" in text          # the resolved transition
    assert "2024-01-06" in text                # a citation is always present
    assert D25.isoformat() in text             # resolved-at date


def test_render_answer_refuses_when_nothing_found():
    text = render_answer(build_struggle_answer(Q, _resolve([Mention("joy", "EmotionalState", D24)])))
    assert "invent" in text.lower()            # graceful refusal, not a fabricated struggle
