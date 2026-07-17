"""Behavior-locking tests for ThemeResolver (wayfinder ticket 08).

Pure — no graph, no LLM. Fixtures mirror the SHAPE of the real anger data (a theme scattered across
an EmotionalState node, a Struggle node, and wording variants). Run:
    python -m pytest tests/test_theme_resolver.py -q
"""

from datetime import date

from mirror.theme_resolver import ThemeResolver, Mention, salient_tokens


D_2024 = date(2024, 1, 6)
D_2025 = date(2025, 1, 3)


# -- tokenization ---------------------------------------------------------------

def test_salient_tokens_drops_filler_keeps_content():
    assert salient_tokens("holding a lot of anger and annoyance") == frozenset({"anger", "annoyance"})


def test_salient_tokens_strips_possessive_and_punctuation():
    assert "uppa" in salient_tokens("Anam's uppa")


# -- the core win: one scattered theme, unified --------------------------------

def _anger_mentions():
    return [
        Mention("anger", "EmotionalState", D_2024, valid_at=D_2024),
        Mention("annoyance", "EmotionalState", D_2024, valid_at=D_2024),
        Mention("holding a lot of anger and annoyance", "Struggle", D_2024, valid_at=D_2024),
        Mention("Persistent anger and annoyance", "Struggle", D_2025, valid_at=D_2025),
    ]


def test_anger_theme_unifies_feeling_struggle_and_wordings():
    themes = ThemeResolver().resolve(_anger_mentions())
    assert len(themes) == 1
    t = themes[0]
    assert t.label == "anger"
    assert set(t.members) == {
        "anger", "annoyance",
        "holding a lot of anger and annoyance", "Persistent anger and annoyance",
    }
    assert t.types == frozenset({"EmotionalState", "Struggle"})


def test_per_year_counts_distinct_entries():
    # anger appears in one 2024 entry and one 2025 entry
    t = ThemeResolver().resolve(_anger_mentions())[0]
    assert t.per_year == {2024: 1, 2025: 1}
    assert t.total_entries == 2


def test_same_node_twice_in_one_entry_counts_once():
    mentions = [
        Mention("anger", "EmotionalState", D_2024),
        Mention("anger", "EmotionalState", D_2024),   # same entry, second edge
        Mention("holding anger", "Struggle", D_2024),
    ]
    t = ThemeResolver().resolve(mentions)[0]
    assert t.per_year == {2024: 1}
    assert t.total_entries == 1


# -- "most" = ranking by distinct-entry count ----------------------------------

def test_themes_ranked_by_total_entries_desc():
    mentions = _anger_mentions() + [
        Mention("avoiding vulnerability by lying", "Struggle", D_2024, valid_at=D_2024),
    ]
    themes = ThemeResolver().resolve(mentions)
    assert [t.label for t in themes][0] == "anger"        # 2 entries > vulnerability's 1
    assert themes[0].total_entries > themes[1].total_entries


# -- "where is it now" from the bi-temporal windows ----------------------------

def test_invalidated_latest_evidence_reads_as_resolved():
    # the anger FEELING was valid in 2024 and invalidated in 2025 → resolved/shifted
    t = ThemeResolver().resolve([
        Mention("anger", "EmotionalState", D_2024, valid_at=D_2024, invalid_at=D_2025),
    ])[0]
    assert t.is_active is False
    assert t.resolved_at == D_2025


def test_recent_valid_evidence_reads_as_active():
    t = ThemeResolver().resolve([
        Mention("anger", "EmotionalState", D_2024, valid_at=D_2024, invalid_at=D_2025),
        Mention("Persistent anger", "Struggle", D_2025, valid_at=D_2025),   # still named in 2025
    ])[0]
    assert t.is_active is True
    assert t.resolved_at is None


# -- guardrails: no false merges -----------------------------------------------

def test_unrelated_struggles_do_not_chain_on_filler_words():
    # both start with the filler "difficulty" but share no CONTENT word → must stay separate
    themes = ThemeResolver().resolve([
        Mention("difficulty appreciating others' work", "Struggle", D_2024),
        Mention("difficulty empathising at depth", "Struggle", D_2024),
    ])
    assert len(themes) == 2


def test_documents_synonym_limit_empathy_not_merged():
    # HONEST limitation: deterministic rules can't unify true synonyms. These stay separate; the
    # user corrects it via the transparency loop. (If this ever passes as 1, we gained semantics.)
    themes = ThemeResolver().resolve([
        Mention("lack of deep empathy", "Struggle", D_2024),
        Mention("difficulty empathising at depth", "Struggle", D_2024),
    ])
    assert len(themes) == 2


def test_empty_input():
    assert ThemeResolver().resolve([]) == []
