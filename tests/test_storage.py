from __future__ import annotations

from pathlib import Path

from argus.storage.db import Storage, build_fts_query


def test_build_fts_query_drops_stopwords_and_ors():
    q = build_fts_query("where is the spare key")
    assert q is not None
    assert "where" not in q
    assert "spare" in q
    assert "key" in q
    assert " OR " in q


def test_build_fts_query_splits_hyphen():
    q = build_fts_query("spare-key")
    assert q == "spare OR key" or ("spare" in q and "key" in q)


def test_search_notes_natural_language(tmp_path: Path):
    store = Storage(tmp_path / "notes.db")
    store.add_note("The spare key is in the kitchen drawer", user_id="owner")

    for query in ("spare key", "where is the spare key", "keys", "spare-key"):
        rows = store.search_notes(query, user_id="owner")
        assert rows, f"expected hit for {query!r}"
        assert "spare key" in rows[0]["content"].lower() or "key" in rows[0]["content"].lower()

    store.close()


def test_tool_calls_round_trip(tmp_path: Path):
    store = Storage(tmp_path / "msg.db")
    store.create_session("s1", "owner", "dev")
    store.add_message(
        "s1",
        "assistant",
        None,
        tool_calls=[{"id": "c1", "name": "get_time", "arguments": {}}],
    )
    store.add_message("s1", "tool", "noon", tool_call_id="c1")
    rows = store.list_messages("s1")
    assert rows[0]["tool_calls"][0]["id"] == "c1"
    assert rows[1]["tool_call_id"] == "c1"
    store.close()
