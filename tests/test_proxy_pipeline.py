import json

import httpx2
from fastapi.testclient import TestClient


def _patch_transport(monkeypatch, handler):
    transport = httpx2.MockTransport(handler)
    real_init = httpx2.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx2.AsyncClient, "__init__", patched_init)


def test_toolscall_capture_persists_to_db(monkeypatch, tmp_path):
    from proxy import proxy as proxy_mod

    db_file = tmp_path / "capture.db"
    monkeypatch.setattr(proxy_mod, "DB_PATH", str(db_file))

    def handler(request):
        return httpx2.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1,
                  "result": {"content": [{"type": "text", "text": "ok"}]}},
        )

    _patch_transport(monkeypatch, handler)

    call = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "send_email", "arguments": {"to": "x@y.com"}},
    }

    with TestClient(proxy_mod.app) as client:
        resp = client.post(
            "/mcp/upstream_host/mcp",
            json=call,
            headers={"mcp-session-id": "sess-123"},
        )
        assert resp.status_code == 200

    # Row landed in the DB the CLI reads.
    from storage import db as db_mod
    import asyncio

    rows = asyncio.run(db_mod.list_calls(str(db_file)))
    assert len(rows) == 1
    record = dict(zip(
        ["id", "session_id", "ts", "direction", "tool_name",
         "input", "output", "latency_ms", "status", "flags"],
        rows[0],
    ))
    assert record["session_id"] == "sess-123"
    assert record["tool_name"] == "send_email"
    assert record["status"] == "success"
    assert json.loads(record["input"]) == call["params"]
    assert "content" in record["output"]


def test_non_toolscall_not_persisted(monkeypatch, tmp_path):
    from proxy import proxy as proxy_mod

    db_file = tmp_path / "capture2.db"
    monkeypatch.setattr(proxy_mod, "DB_PATH", str(db_file))

    def handler(request):
        return httpx2.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "pong"})

    _patch_transport(monkeypatch, handler)

    with TestClient(proxy_mod.app) as client:
        resp = client.post("/mcp/upstream_host/mcp",
                           json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 200

    from storage import db as db_mod
    import asyncio

    asyncio.run(proxy_mod._ensure_db(str(db_file)))
    rows = asyncio.run(db_mod.list_calls(str(db_file)))
    assert rows == []


def test_export_returns_db_rows(monkeypatch, tmp_path):
    from proxy import proxy as proxy_mod
    from storage import db as db_mod
    import asyncio

    db_file = tmp_path / "export.db"
    monkeypatch.setattr(proxy_mod, "DB_PATH", str(db_file))

    record = {
        "id": "abc", "session_id": "s1", "ts": "2026-07-07T00:00:00",
        "direction": "response", "tool_name": "send_email",
        "input": "{}", "output": "{}", "latency_ms": 5,
        "status": "success", "flags": "[]",
    }
    asyncio.run(proxy_mod._ensure_db(str(db_file)))
    asyncio.run(db_mod.insert_call(str(db_file), record))

    with TestClient(proxy_mod.app) as client:
        resp = client.get("/api/export")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tool_name"] == "send_email"
