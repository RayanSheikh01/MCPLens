import asyncio
import json
import re

import aiosqlite
import click

DEFAULT_DB = "sessions.db"

# Tool names matching this are treated as state-changing and prompted under --confirm.
MUTATING = re.compile(
    r"(send|create|update|delete|remove|add|move|set|complete)", re.IGNORECASE
)

CALL_COLUMNS = [
    "id", "session_id", "ts", "direction", "tool_name",
    "input", "output", "latency_ms", "status", "flags",
]


def app():
    # Serve the proxy app directly; it already exposes /mcp/{server}/{path},
    # /ws, /api/* and the dashboard at /. Mounting it under a prefix would
    # double the /mcp path segment and break forwarding.
    from proxy.proxy import app as proxy_app

    return proxy_app


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


async def _replay_records(records, confirm=False):
    from proxy.replay import fire_call

    for r in records:
        tool = r["tool_name"] or ""
        if confirm and MUTATING.search(tool):
            if not click.confirm(f"Fire mutating call '{tool}'?"):
                click.echo(f"Skipping {tool}")
                continue
        click.echo(f"Firing request: {tool}")
        await fire_call(r)


@main.command()
@click.option("--session", "session", default=None, help="Filter by session id.")
@click.option("--dry-run", "dry_run", is_flag=True,
              help="Show what would fire without sending anything.")
@click.option("--confirm", "confirm", is_flag=True,
              help="Confirm and fire the captured requests.")
@click.option("--db", "db_path", default=DEFAULT_DB, help="Database path.")
def replay(session, dry_run, confirm, db_path):
    """Replay captured calls for a session."""
    records = asyncio.run(_fetch_calls(db_path, session))
    if dry_run:
        for r in records:
            click.echo(f"Dry run: would fire {r['tool_name']}")
        click.echo(f"Dry run complete: {len(records)} call(s) would fire")
        return
    asyncio.run(_replay_records(records, confirm=confirm))


@main.command()
@click.option("--port", default=8000, help="Port to serve on.")
def start(port):
    """Run the inspector proxy server."""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, factory=True)


if __name__ == "__main__":
    main()
