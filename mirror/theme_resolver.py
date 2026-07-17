"""ThemeResolver — a deterministic, non-destructive view that unifies a scattered theme.

The problem (wayfinder ticket 08): one real theme — "anger" — is smeared across the graph as an
`EmotionalState` node ("anger"), a `Struggle` node ("holding a lot of anger and annoyance"), and
several wordings of that struggle, with triggers/transitions hanging off different pieces. Ranking
raw nodes therefore splits and under-counts it.

This resolver groups node *mentions* into canonical **themes** and aggregates what the target
question needs — per-year distinct-entry counts (the "most" metric) and a current status derived
from the bi-temporal windows ("where is it now"). It is:

  * **deterministic** — pure token rules + union-find, no LLM, so it's stable run-to-run and fully
    unit-testable (and adds no cost/variance);
  * **non-destructive** — it's a VIEW over the graph, never a merge, so a wrong grouping costs
    nothing to fix (change a rule / user correction), unlike a permanent ingest-time merge;
  * **honest about its limit** — it unifies clear shared-word cases (all "anger" nodes) but NOT
    true synonyms (empathy vs empathising); that semantic residual is surfaced for user correction,
    not silently guessed.

Input is a list of plain `Mention`s (populated by the MemoryEngine from Graphiti queries), so the
resolver has no Graphiti dependency and tests need no graph.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date

# Structural + journal/struggle FILLER words. Removing these is what stops unrelated struggles
# from chaining together on a generic word ("difficulty", "holding") — only CONTENT words
# (anger, empathy, vulnerability) drive grouping.
STOPWORDS = frozenset("""
a an the of to at in on and or but my me i we you it its this that these those with by for
is was were be being been am are has have had do does did not no more less too so very
holding hold lot persistent difficulty lack avoidance avoiding avoid getting get tendency
still always constant sense feeling feel felt being toward towards about into onto over
""".split())

# Generic light stemmer — strips a few common suffixes so 'appreciating' ~ 'appreciate-ish'.
# Deliberately conservative; true synonym resolution (empathy/empathising) is out of scope.
_SUFFIXES = ("ously", "ing", "edly", "ed", "ness", "ies", "es", "s")


def _stem(tok: str) -> str:
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def salient_tokens(name: str) -> frozenset[str]:
    """Content tokens of a node name: lowercase, strip possessives/punctuation, drop stopwords,
    light-stem. E.g. "holding a lot of anger and annoyance" -> {anger, annoyance}."""
    cleaned = "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in name)
    toks = {_stem(t) for t in cleaned.split() if t and t not in STOPWORDS}
    return frozenset(t for t in toks if t not in STOPWORDS)


@dataclass(frozen=True)
class Mention:
    """One appearance of a node in the graph, flattened to what the resolver needs — no Graphiti
    types. `invalid_at` set = this fact was bi-temporally invalidated (the then→now signal)."""
    node: str
    node_type: str          # "Struggle" | "EmotionalState" | ...
    entry_date: _date       # the entry this came from (for per-year counts)
    valid_at: _date | None = None
    invalid_at: _date | None = None


@dataclass(frozen=True)
class Theme:
    label: str                          # canonical label = most common content token
    members: tuple[str, ...]            # the distinct node names grouped in
    types: frozenset[str]               # node types spanned (e.g. {Struggle, EmotionalState})
    per_year: dict[int, int]            # distinct-entry count per year
    total_entries: int                  # distinct entries across all years ("most" metric)
    entry_dates: tuple[_date, ...]      # the distinct entries backing it (for citations)
    first_date: _date
    last_date: _date
    is_active: bool                     # latest evidence not invalidated → still current
    resolved_at: _date | None           # if not active, when its last fact was invalidated


class _UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


class ThemeResolver:
    def resolve(self, mentions: list[Mention]) -> list[Theme]:
        """Group mentions into themes, ranked by distinct-entry count (descending), ties broken by
        label for determinism."""
        if not mentions:
            return []

        names = sorted({m.node for m in mentions})
        tokens = {name: salient_tokens(name) for name in names}

        # Union-find: two node names are the same theme if they share any content token.
        uf = _UnionFind(names)
        token_to_names: dict[str, list[str]] = defaultdict(list)
        for name in names:
            for tok in tokens[name]:
                token_to_names[tok].append(name)
        for shared_names in token_to_names.values():
            first = shared_names[0]
            for other in shared_names[1:]:
                uf.union(first, other)

        groups: dict[str, list[str]] = defaultdict(list)
        for name in names:
            groups[uf.find(name)].append(name)

        by_name: dict[str, list[Mention]] = defaultdict(list)
        for m in mentions:
            by_name[m.node].append(m)

        themes = [self._build_theme(members, by_name, tokens) for members in groups.values()]
        themes.sort(key=lambda t: (-t.total_entries, t.label))
        return themes

    def _build_theme(self, members, by_name, tokens) -> Theme:
        member_mentions = [m for name in members for m in by_name[name]]

        # per-year DISTINCT entries (a node mentioned twice in one entry counts once)
        years: dict[int, set[_date]] = defaultdict(set)
        for m in member_mentions:
            years[m.entry_date.year].add(m.entry_date)
        per_year = {y: len(ds) for y, ds in years.items()}
        all_dates = {m.entry_date for m in member_mentions}

        # label = most frequent content token across the group (tie-break alphabetical)
        tok_counts: dict[str, int] = defaultdict(int)
        for name in members:
            for tok in tokens[name]:
                tok_counts[tok] += 1
        label = min(tok_counts, key=lambda t: (-tok_counts[t], t)) if tok_counts else members[0]

        # "where is it now": latest evidence's validity. If the most recent mention was
        # invalidated, the theme has resolved/shifted; else it's still active.
        def when(m: Mention) -> _date:
            return m.valid_at or m.entry_date
        latest = max(when(m) for m in member_mentions)
        latest_mentions = [m for m in member_mentions if when(m) == latest]
        is_active = any(m.invalid_at is None for m in latest_mentions)
        resolved_at = None if is_active else max(m.invalid_at for m in latest_mentions)

        return Theme(
            label=label,
            members=tuple(sorted(members)),
            types=frozenset(m.node_type for m in member_mentions),
            per_year=dict(sorted(per_year.items())),
            total_entries=len(all_dates),
            entry_dates=tuple(sorted(all_dates)),
            first_date=min(all_dates),
            last_date=max(all_dates),
            is_active=is_active,
            resolved_at=resolved_at,
        )
