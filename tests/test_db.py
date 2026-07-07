import aiosqlite
import pytest

from storage.db import insert_call, list_calls, get_flags, get_session


async def _make_db(path):
    """Create the calls+sessions schema at `path` (init_db hardcodes its own path)."""
    db = await aiosqlite.connect(path)
    await db.execute(
        """CREATE TABLE calls (
            id TEXT PRIMARY KEY, session_id TEXT, ts TIMESTAMP, direction TEXT,
            tool_name TEXT, input TEXT, output TEXT, latency_ms INTEGER,
            status TEXT, flags TEXT)"""
    )
    await db.execute(
        """CREATE TABLE sessions (
            id TEXT PRIMARY KEY, server TEXT, started_at TIMESTAMP,
            last_at TIMESTAMP, call_count INTEGER)"""
    )
    await db.commit()
    await db.close()


def _record(cid, sid="s1", tool="search", status="success", flags=""):
    return {
        "id": cid, "session_id": sid, "ts": 1234567890, "direction": "response",
        "tool_name": tool, "input": "{}", "output": "{}", "latency_ms": 10,
        "status": status, "flags": flags,
    }


@pytest.fixture
async def db_path(tmp_path):
    p = str(tmp_path / "t.db")
    await _make_db(p)
    return p


async def test_insert_and_list_roundtrip(db_path):
    await insert_call(db_path, _record("c1"))
    rows = await list_calls(db_path)
    assert len(rows) == 1
    assert rows[0][0] == "c1"


async def test_list_calls_filter(db_path):
    await insert_call(db_path, _record("c1", tool="search"))
    await insert_call(db_path, _record("c2", tool="send_email"))
    rows = await list_calls(db_path, tool_name="send_email")
    assert len(rows) == 1
    assert rows[0][4] == "send_email"


async def test_get_flags(db_path):
    await insert_call(db_path, _record("c1", flags="SLOW_CALL"))
    await insert_call(db_path, _record("c2", flags=""))
    flags = await get_flags(db_path, "s1")
    assert flags == ["SLOW_CALL", ""]


async def test_get_session_missing(db_path):
    assert await get_session(db_path, "nope") is None
