import asyncio
import json

import pytest
from click.testing import CliRunner

from main import main as cli
from storage.db import insert_call

SID = "sess-1"


def _seed(db_path):
    async def go():
        # create tables at db_path
        import aiosqlite
        db = await aiosqlite.connect(db_path)
        await db.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY, session_id TEXT, ts TIMESTAMP, direction TEXT,
            tool_name TEXT, input TEXT, output TEXT, latency_ms INTEGER,
            status TEXT, flags TEXT
        )''')
        await db.commit()
        await db.close()

        await insert_call(db_path, {
            "id": "c1", "session_id": SID, "ts": "2026-07-06T00:00:00",
            "direction": "response", "tool_name": "search", "input": "{}",
            "output": "{}", "latency_ms": 50, "status": "ok", "flags": "[]",
        })
        await insert_call(db_path, {
            "id": "c2", "session_id": SID, "ts": "2026-07-06T00:00:01",
            "direction": "response", "tool_name": "send_email", "input": "{}",
            "output": "{}", "latency_ms": 3000, "status": "error",
            "flags": '["SLOW_CALL"]',
        })

    asyncio.run(go())


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed(db_path)
    return db_path


def test_inspect_prints_calls(seeded_db):
    """inspect --session <id> prints the calls table"""
    result = CliRunner().invoke(cli, ["inspect", "--db", seeded_db, "--session", SID])
    assert result.exit_code == 0
    assert "search" in result.output
    assert "send_email" in result.output


def test_flags_lists_only_flagged(seeded_db):
    """flags --session <id> lists only flagged calls"""
    result = CliRunner().invoke(cli, ["flags", "--db", seeded_db, "--session", SID])
    assert result.exit_code == 0
    assert "send_email" in result.output
    assert "search" not in result.output


def test_export_dumps_json(seeded_db, tmp_path):
    """export --session <id> --output f.json dumps all calls as JSON"""
    out = tmp_path / "calls.json"
    result = CliRunner().invoke(
        cli, ["export", "--db", seeded_db, "--session", SID, "--output", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data) == 2
    assert {r["tool_name"] for r in data} == {"search", "send_email"}
