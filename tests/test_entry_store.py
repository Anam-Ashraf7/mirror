"""Behavior-locking tests for EntryStore (wayfinder ticket 10: no boundary ships without them).

Pure and hermetic — every test uses a temp dir and synthetic text, never a real journal entry.
Run: python -m pytest tests/test_entry_store.py -q
"""

from datetime import date

import pytest

from mirror.entry_store import EntryStore, Entry, content_hash


@pytest.fixture
def store(tmp_path):
    return EntryStore(root=tmp_path)


# -- identity: date, exact & deterministic --------------------------------------

def test_put_and_get_roundtrip(store):
    e = store.put(date(2024, 1, 6), "sat 20 min, felt settled")
    got = store.get(date(2024, 1, 6))
    assert got == e
    assert got.date == date(2024, 1, 6)
    assert got.text == "sat 20 min, felt settled"
    assert got.source_name == "2024-01-06.md"


def test_get_missing_returns_none(store):
    assert store.get(date(1999, 1, 1)) is None


def test_identity_is_date_not_content(store):
    # Two DIFFERENT days with IDENTICAL text must stay two distinct entries — never fuzzily
    # merged. (Fuzzy matching belongs at the concept level, never at the entry level.)
    store.put(date(2024, 3, 1), "meditated, calm evening")
    store.put(date(2025, 3, 1), "meditated, calm evening")
    entries = store.list()
    assert len(entries) == 2
    assert {e.date for e in entries} == {date(2024, 3, 1), date(2025, 3, 1)}


def test_put_replaces_same_date(store):
    store.put(date(2024, 1, 6), "first version")
    store.put(date(2024, 1, 6), "corrected version")
    assert len(store.list()) == 1
    assert store.get(date(2024, 1, 6)).text == "corrected version"


# -- versioning: content_hash detects real edits, ignores cosmetic churn ---------

def test_content_hash_ignores_cosmetic_whitespace():
    a = "line one\nline two"
    b = "  \nline one   \r\nline two\t\n\n"   # trailing spaces, CRLF, surrounding blank lines
    assert content_hash(a) == content_hash(b)


def test_content_hash_changes_on_real_edit():
    assert content_hash("I felt angry") != content_hash("I felt calm")


def test_edit_changes_version_not_identity(store):
    v1 = store.put(date(2024, 1, 6), "I felt angry at uppa")
    v2 = store.put(date(2024, 1, 6), "I felt annoyed at uppa")   # a genuine text edit
    assert v1.date == v2.date                    # identity unchanged
    assert v1.content_hash != v2.content_hash    # version changed → derive layer re-derives


def test_cosmetic_reput_keeps_same_hash(store):
    v1 = store.put(date(2024, 1, 6), "sat quietly")
    v2 = store.put(date(2024, 1, 6), "  sat quietly  \n")   # only whitespace differs
    assert v1.content_hash == v2.content_hash    # NOT a real edit → no needless re-derive


# -- ordering: oldest-first everywhere ------------------------------------------

def test_list_is_oldest_first(store):
    for d in [date(2025, 9, 17), date(2024, 1, 6), date(2025, 1, 3)]:
        store.put(d, f"entry {d.isoformat()}")
    assert [e.date for e in store.list()] == [
        date(2024, 1, 6), date(2025, 1, 3), date(2025, 9, 17),
    ]


def test_entries_from_returns_inclusive_tail_oldest_first(store):
    for d in [date(2024, 1, 6), date(2025, 1, 3), date(2025, 9, 17)]:
        store.put(d, "x")
    tail = store.entries_from(date(2025, 1, 3))
    assert [e.date for e in tail] == [date(2025, 1, 3), date(2025, 9, 17)]


# -- reading externally-created files (seeding from data/transcripts/) -----------

def test_reads_externally_written_proofread_files(tmp_path):
    # Simulates seeding from already-proofread transcript files not written via put().
    (tmp_path / "2024-01-06.md").write_text("proofread body", encoding="utf-8")
    store = EntryStore(root=tmp_path)
    e = store.get(date(2024, 1, 6))
    assert e is not None and e.text == "proofread body"
    assert e.content_hash == content_hash("proofread body")


def test_list_skips_undated_files(tmp_path):
    (tmp_path / "2024-01-06.md").write_text("dated", encoding="utf-8")
    (tmp_path / "README.md").write_text("not an entry", encoding="utf-8")
    store = EntryStore(root=tmp_path)
    assert [e.date for e in store.list()] == [date(2024, 1, 6)]


def test_missing_root_lists_empty(tmp_path):
    store = EntryStore(root=tmp_path / "does-not-exist")
    assert store.list() == []
