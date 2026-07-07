import json
import uuid

import aiosqlite
import fastapi
import httpx2

from analyser import analyser
from proxy.hub import Hub
from proxy.interceptor import Pairer, parse_jsonrpc
from storage import db as storage_db

app = fastapi.FastAPI()
hub = Hub()


def _load_config():
    """Load config.yaml if present; tolerate its absence (tests, fresh checkout)."""
    try:
        import config as config_mod
        return config_mod.load_config()
    except (FileNotFoundError, ImportError, Exception):
        return {}


_CFG = _load_config()
SERVERS = _CFG.get("servers", {}) if isinstance(_CFG, dict) else {}
DB_PATH = (
    _CFG.get("storage", {}).get("db_path", "sessions.db")
    if isinstance(_CFG, dict) else "sessions.db"
)

CALL_COLUMNS = [
    "id", "session_id", "ts", "direction", "tool_name",
    "input", "output", "latency_ms", "status", "flags",
]


def _resolve_url(server: str, path: str) -> str:
    """Map a server name to its upstream URL.

    Configured servers use their `upstream` from config.yaml; unknown names
    fall back to treating the name as a host (`http://<server>/<path>`), which
    keeps direct host:port targeting and the existing test behaviour working.
    """
    entry = SERVERS.get(server)
    if entry and entry.get("upstream"):
        base = entry["upstream"].rstrip("/")
        return f"{base}/{path}" if path else base
    return f"http://{server}/{path}"


async def _ensure_db(path: str):
    """Create the calls table if absent so capture can persist to any db path."""
    db = await aiosqlite.connect(path)
    try:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            ts TIMESTAMP,
            direction TEXT,
            tool_name TEXT,
            input TEXT,
            output TEXT,
            latency_ms INTEGER,
            status TEXT,
            flags TEXT
        )
        ''')
        await db.commit()
    finally:
        await db.close()


def _flag(record, history):
    """Run the analyser over a paired record; store flags as JSON text.

    Tool schema is keyed by the record's tool name so a captured tool is not
    reported as "unknown".
    """
    flags = analyser.analyse(record, history, {record["tool_name"]: {}})
    record["flags"] = json.dumps(flags)
    return record


async def _capture(record):
    """Persist a CallRecord to the DB the CLI/dashboard read from."""
    await _ensure_db(DB_PATH)
    await storage_db.insert_call(DB_PATH, record)


@app.api_route("/mcp/{server}/{path:path}", methods=["GET", "POST", "DELETE"])
async def forward(server, path, request: fastapi.Request):
    """
    Forward the request to the resolved upstream, capturing the JSON-RPC call,
    persisting paired tools/call records, and broadcasting to WebSocket clients.
    """
    url = _resolve_url(server, path)
    headers = dict(request.headers)
    method = request.method
    body = await request.body()
    session_id = request.headers.get("mcp-session-id") or uuid.uuid4().hex

    # Pair requests with their responses. Only tools/call requests yield
    # persisted records; other traffic is broadcast raw for the live tail.
    pairer = Pairer()
    ctx = {"session_id": session_id}
    req_objs = parse_jsonrpc(body)
    is_toolscall = any(o.get("method") == "tools/call" for o in req_objs)
    for obj in req_objs:
        pairer.on_request(obj, ctx)

    if not is_toolscall and req_objs:
        # Non tools/call: no record to build, so surface the raw call live.
        await hub.broadcast(req_objs[0] if len(req_objs) == 1 else req_objs)

    client = httpx2.AsyncClient()
    req = client.build_request(method, url, headers=headers, content=body)
    response = await client.send(req, stream=True)
    content_type = response.headers.get("content-type", "")

    if content_type.startswith("text/event-stream"):
        # Stream the SSE response back while teeing each chunk into an SSE
        # parser, broadcasting captured JSON-RPC messages to WebSocket clients.
        async def event_stream():
            buffer = ""
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    buffer += chunk.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        try:
                            await hub.broadcast(json.loads(data))
                        except (json.JSONDecodeError, ValueError):
                            pass
            finally:
                await response.aclose()
                await client.aclose()

        return fastapi.responses.StreamingResponse(
            event_stream(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="text/event-stream",
        )

    content = await response.aread()
    await response.aclose()
    await client.aclose()

    # Pair response↔request; flag, persist, and broadcast enriched records.
    for resp_obj in parse_jsonrpc(content):
        for record in pairer.on_response(resp_obj, ctx):
            _flag(record, [])
            await _capture(record)
            await hub.broadcast(record)

    return fastapi.Response(content=content, status_code=response.status_code, headers=dict(response.headers))


@app.websocket("/ws")
async def websocket_endpoint(websocket: fastapi.WebSocket):
    """
    Register queue, stream captured calls
    """
    await websocket.accept()
    queue = hub.register()
    try:
        while True:
            call = await queue.get()
            await websocket.send_json(call)
    except fastapi.WebSocketDisconnect:
        pass
    finally:
        hub.unregister(queue)


@app.post("/api/replay")
async def replay_call(call: dict):
    """
    Replay a captured JSON-RPC call by forwarding it to the appropriate server.
    """
    server = call.get("server")
    path = call.get("path")
    if not server or not path:
        return fastapi.Response(content="Missing 'server' or 'path' in call", status_code=400)

    url = _resolve_url(server, path)
    headers = call.get("headers", {})
    body = json.dumps(call.get("body", {})).encode("utf-8")

    client = httpx2.AsyncClient()
    req = client.build_request("POST", url, headers=headers, content=body)
    response = await client.send(req)
    content = await response.aread()
    await response.aclose()
    await client.aclose()

    return fastapi.Response(content=content, status_code=response.status_code, headers=dict(response.headers))


@app.get("/api/export")
async def export_calls():
    """
    Export captured calls from the database as JSON.
    """
    await _ensure_db(DB_PATH)
    rows = await storage_db.list_calls(DB_PATH)
    calls = [dict(zip(CALL_COLUMNS, row)) for row in rows]
    return fastapi.responses.JSONResponse(content=calls)


@app.get("/")
async def root():
    return fastapi.responses.FileResponse("dashboard/index.html")
