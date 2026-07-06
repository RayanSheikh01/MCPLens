import asyncio
import json

import aiosqlite
import click

DEFAULT_DB = "sessions.db"

CALL_COLUMNS = [
    "id", "session_id", "ts", "direction", "tool_name",
    "input", "output", "latency_ms", "status", "flags",
]


def app():
    from fastapi import FastAPI
    from proxy.proxy import app as proxy_app

    app = FastAPI()
    app.mount("/mcp", proxy_app)
    return app


async def _ensure_calls_table(db):
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


def _is_flagged(flags_value):
    if not flags_value:
        return False
    return flags_value not in ("[]", "null")


async def _fetch_calls(db_path, session_id=None, flagged_only=False):
    db = await aiosqlite.connect(db_path)
    try:
        await _ensure_calls_table(db)
        query = "SELECT * FROM calls"
        values = []
        if session_id:
            query += " WHERE session_id = ?"
            values.append(session_id)
        async with db.execute(query, values) as cursor:
            rows = await cursor.fetchall()
    finally:
        await db.close()

    records = [dict(zip(CALL_COLUMNS, row)) for row in rows]
    if flagged_only:
        records = [r for r in records if _is_flagged(r["flags"])]
    return records


def _print_calls(records):
    if not records:
        click.echo("no calls found")
        return
    for r in records:
        click.echo(
            f"{r['ts']} {r['tool_name']} status={r['status']} "
            f"latency={r['latency_ms']}ms flags={r['flags']}"
        )


@click.group()
def main():
    """MCP Traffic Inspector CLI."""


@main.command()
@click.option("--session", "session", default=None, help="Filter by session id.")
@click.option("--flags", "flags_only", is_flag=True, help="Show only flagged calls.")
@click.option("--export", "export", type=click.Path(), default=None,
              help="Write results as JSON to this path.")
@click.option("--db", "db_path", default=DEFAULT_DB, help="Database path.")
def inspect(session, flags_only, export, db_path):
    """Print captured calls; optionally filter flagged and export JSON."""
    records = asyncio.run(_fetch_calls(db_path, session, flagged_only=flags_only))
    _print_calls(records)
    if export:
        with open(export, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        click.echo(f"exported {len(records)} calls to {export}")


@main.command()
@click.option("--session", "session", default=None, help="Filter by session id.")
@click.option("--db", "db_path", default=DEFAULT_DB, help="Database path.")
def flags(session, db_path):
    """List flagged calls."""
    records = asyncio.run(_fetch_calls(db_path, session, flagged_only=True))
    _print_calls(records)


@main.command()
@click.option("--session", "session", default=None, help="Filter by session id.")
@click.option("--output", "output", type=click.Path(), required=True,
              help="Output JSON path.")
@click.option("--db", "db_path", default=DEFAULT_DB, help="Database path.")
def export(session, output, db_path):
    """Dump calls to a JSON file."""
    records = asyncio.run(_fetch_calls(db_path, session))
    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    click.echo(f"exported {len(records)} calls to {output}")


@main.command()
@click.option("--port", default=8000, help="Port to serve on.")
def start(port):
    """Run the inspector proxy server."""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, factory=True)


if __name__ == "__main__":
    main()
