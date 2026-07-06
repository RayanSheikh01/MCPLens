# MCP Traffic Inspector

A debugging reverse-proxy for the [Model Context Protocol](https://modelcontextprotocol.io).
It sits between an MCP client and an upstream MCP server, capturing every
`tools/call` request/response pair, flagging suspicious behaviour, streaming
traffic live to a browser dashboard, and letting you replay captured calls.

## Features

- **Capture** — transparent proxy over JSON-RPC (`POST`/`GET`/`DELETE`) and
  `text/event-stream` (SSE), with responses paired to requests by id and
  latency computed per call.
- **Persist** — every call is written to SQLite (`sessions.db`).
- **Analyse** — automatic flags on captured calls (high latency, repeated
  failures, unexpected schema, possible prompt injection, data exfiltration).
- **Live dashboard** — WebSocket-fed table with filters, a JSON detail panel,
  and colored flag badges.
- **Replay** — re-fire captured calls with fresh auth from config; dry-run by
  default, per-call confirmation for state-changing tools.
- **Export** — dump a session to JSON.

## Requirements

- Python >= 3.10

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -e ".[dev]"
```

## Configuration

Copy the template and fill in real upstream URLs and tokens:

```bash
cp config.example.yaml config.yaml
```

```yaml
servers:
  mock:
    upstream: "http://localhost:9000/mcp"
    auth: "Bearer test-token"

storage:
  db_path: "./inspector.db"
```

> **Security note:** `config.yaml` holds bearer tokens and is **git-ignored**.
> Only `config.example.yaml` (no secrets) is committed. Never commit real
> tokens. Replay re-reads auth from `config.yaml` at fire time, so rotating a
> token there is enough.

## Usage

After `pip install -e .`, run commands with the `mcp-inspector` entry point
(all commands accept `--db` to point at a different SQLite file; default
`sessions.db`).

```text
start   --port 8000                          # run the proxy + dashboard
inspect --session <id> [--flags] [--export f.json]
flags   --session <id>                       # list flagged calls only
export  --session <id> --output f.json       # dump session as JSON
replay  --session <id> [--dry-run|--confirm] # replay captured calls
```

Start the proxy and open the dashboard:

```bash
mcp-inspector start --port 8000
# dashboard at http://localhost:8000/
```

Point your MCP client at `http://localhost:8000/mcp/<server>/...` where
`<server>` matches a key under `servers:` in `config.yaml`. Traffic is
forwarded to that upstream and captured en route.

Inspect and replay a session:

```bash
mcp-inspector inspect --session <id>
mcp-inspector flags   --session <id>
mcp-inspector replay  --session <id> --dry-run     # preview, fires nothing
mcp-inspector replay  --session <id> --confirm     # re-fire (prompts on mutating tools)
mcp-inspector export  --session <id> --output session.json
```

## Flags

| Flag | Rule |
| --- | --- |
| `SLOW_CALL` | latency over threshold |
| `REPEATED_FAILURE` | recent calls to the same tool all errored |
| `UNEXPECTED_SCHEMA` | output fails validation against the tool's output schema |
| `POSSIBLE_INJECTION` | output text matches prompt-injection patterns |
| `DATA_EXFIL` | output matches email / key / base64 / credential patterns |

## Testing

```bash
pytest -q
```

Full suite (unit + integration, including a bundled mock MCP server under
`tests/mock_mcp.py`) is green.

## End-to-end verification

1. Run the bundled mock MCP server; point `config.yaml` `upstream` at it.
2. `mcp-inspector start --port 8080`; open `http://localhost:8080/`.
3. `curl` a `tools/call` at `/mcp/<server>` (one slow, one failing 3×, one with
   injection-like text) → confirm the row persists in SQLite, appears live on
   the dashboard, and shows the correct flags.
4. `mcp-inspector flags --session <id>` lists the expected flags.
5. `mcp-inspector replay --session <id> --dry-run` previews only (nothing fires).
6. `mcp-inspector replay --session <id> --confirm` re-fires; mutating tools
   prompt; auth is read fresh from config.
7. `mcp-inspector export --session <id> --output session.json` → valid JSON.
8. `pytest` green.

## Project layout

```text
main.py                CLI (click) — start / inspect / flags / export / replay
config.py              config.yaml loader
proxy/proxy.py         FastAPI proxy, WebSocket hub, dashboard, replay/export API
proxy/interceptor.py   JSON-RPC parse + request↔response pairing
proxy/hub.py           in-process WebSocket broadcast
proxy/sse.py           SSE data-line JSON extraction
proxy/replay.py        replay engine
analyser/analyser.py   flag rules
storage/db.py          SQLite schema + queries
storage/sessions.py    session lifecycle
dashboard/index.html   single-file vanilla-JS dashboard
tests/                 pytest suite + mock MCP server
```
