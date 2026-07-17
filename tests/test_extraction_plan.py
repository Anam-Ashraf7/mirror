"""Behavior-locking tests for the re-derive-forward algorithm (wayfinder ticket 08).

Pure — no graph, no LLM, no cost. This is the risky new logic of Phase 1; the live ingest itself
is already proven by the prototype. Run: python -m pytest tests/test_extraction_plan.py -q
"""

from datetime import date

from mirror.extraction import plan_sync, episode_name, parse_episode_name


D1, D2, D3 = date(2024, 1, 6), date(2025, 1, 3), date(2025, 9, 17)


# -- episode naming round-trips (the graph's self-description) -------------------

def test_episode_name_roundtrip_single_pass():
    name = episode_name(D1, "ab12cd34ef5678", pass_i=0, passes=1)
    assert name == "journal-2024-01-06-ab12cd34ef56"
    assert parse_episode_name(name) == (D1, "ab12cd34ef56")


def test_episode_name_roundtrip_ensemble_pass():
    name = episode_name(D1, "ab12cd34ef5678", pass_i=1, passes=3)
    assert name == "journal-2024-01-06-ab12cd34ef56-p2"
    assert parse_episode_name(name) == (D1, "ab12cd34ef56")


def test_parse_rejects_foreign_episode_names():
    assert parse_episode_name("some-other-episode") is None
    assert parse_episode_name("journal-2024-01-06") is None       # no hash
    assert parse_episode_name("journal-not-a-date-abcdef123456") is None


# -- plan_sync: the re-derive-forward decision ----------------------------------

def test_first_run_ingests_everything_removes_nothing():
    desired = [(D1, "h1"), (D2, "h2"), (D3, "h3")]
    plan = plan_sync(desired, existing={})
    assert plan.rederive_from == D1
    assert plan.ingest == [D1, D2, D3]
    assert plan.remove == []


def test_fully_current_graph_is_noop():
    desired = [(D1, "h1"), (D2, "h2"), (D3, "h3")]
    existing = {D1: {"h1"}, D2: {"h2"}, D3: {"h3"}}
    plan = plan_sync(desired, existing)
    assert plan.is_noop
    assert plan.ingest == [] and plan.remove == []


def test_new_tail_entry_ingests_only_it_removes_nothing():
    desired = [(D1, "h1"), (D2, "h2"), (D3, "h3")]
    existing = {D1: {"h1"}, D2: {"h2"}}          # D3 is brand new at the end
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D3
    assert plan.ingest == [D3]
    assert plan.remove == []                      # nothing after it to redo


def test_edit_middle_rederives_from_there_forward():
    desired = [(D1, "h1"), (D2, "h2new"), (D3, "h3")]
    existing = {D1: {"h1"}, D2: {"h2old"}, D3: {"h3"}}
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D2
    assert plan.ingest == [D2, D3]                # later entry redone too — its links depended on D2
    assert plan.remove == [D2, D3]                # old episodes for the tail cleared first


def test_edit_oldest_rederives_all():
    desired = [(D1, "h1new"), (D2, "h2"), (D3, "h3")]
    existing = {D1: {"h1old"}, D2: {"h2"}, D3: {"h3"}}
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D1
    assert plan.ingest == [D1, D2, D3]
    assert plan.remove == [D1, D2, D3]


def test_backfilled_old_entry_rederives_from_its_date():
    # A previously-missing old entry gets added (backfilling history).
    desired = [(D1, "h1"), (D2, "h2"), (D3, "h3")]
    existing = {D2: {"h2"}, D3: {"h3"}}          # D1 was never ingested
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D1
    assert plan.ingest == [D1, D2, D3]
    assert plan.remove == [D2, D3]               # D1 has nothing to remove; the tail is redone


def test_deleted_middle_entry_is_detected_and_tail_rederived():
    # D2 removed from the store but still orphaned in the graph.
    desired = [(D1, "h1"), (D3, "h3")]
    existing = {D1: {"h1"}, D2: {"h2"}, D3: {"h3"}}
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D2
    assert plan.ingest == [D3]                    # D2 not re-ingested (it's gone)
    assert plan.remove == [D2, D3]                # orphan D2 cleared; D3 redone


def test_deleted_tail_entry_removes_orphan_ingests_nothing():
    desired = [(D1, "h1"), (D2, "h2")]
    existing = {D1: {"h1"}, D2: {"h2"}, D3: {"h3"}}
    plan = plan_sync(desired, existing)
    assert plan.rederive_from == D3
    assert plan.ingest == []
    assert plan.remove == [D3]


def test_stale_old_version_lingering_alongside_current_is_still_noop_free():
    # If the graph somehow holds BOTH an old and current version for D2, the current one matches,
    # so D2 isn't dirty on its own — only genuine mismatches drive a re-derive.
    desired = [(D1, "h1"), (D2, "h2")]
    existing = {D1: {"h1"}, D2: {"h2", "h2old"}}
    plan = plan_sync(desired, existing)
    assert plan.is_noop
