import json
import time
import uuid
from datetime import datetime, timezone


def parse_jsonrpc(raw) -> list[dict]:
    """
    Parse a raw JSON-RPC request or response and return a list of dictionaries representing the calls.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, dict):
        # Single request/response
        return [data]
    elif isinstance(data, list):
        # Batch request/response
        return data
    else:
        return []


class Pairer:
    """Pairs JSON-RPC requests with their responses by id and emits CallRecords.

    Pure/no-I/O: latency is measured from monotonic clock at request time, and
    contextual fields (session_id) are supplied by the caller via ``ctx``.
    Only ``tools/call`` requests are paired, per the interceptor contract.
    """

    def __init__(self):
        self.pending = {}

    def on_request(self, msg, ctx=None):
        """Record pending request(s), keyed by id, with a start timestamp."""
        calls = msg if isinstance(msg, list) else [msg]

        request_ids = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            request_id = call.get("id")
            if request_id is None:
                continue
            self.pending[request_id] = {"call": call, "t_start": time.perf_counter()}
            request_ids.append(request_id)

        if ctx is not None:
            try:
                ctx.setdefault("jsonrpc_request_ids", []).extend(request_ids)
            except AttributeError:
                pass

        return msg

    def on_response(self, msg, ctx=None) -> list[dict]:
        """Pair response(s) with pending tools/call requests → CallRecords."""
        ctx = ctx or {}
        session_id = ctx.get("session_id")
        responses = msg if isinstance(msg, list) else [msg]

        records = []
        for resp in responses:
            if not isinstance(resp, dict):
                continue
            entry = self.pending.pop(resp.get("id"), None)
            if entry is None:
                continue

            req = entry["call"]
            if req.get("method") != "tools/call":
                continue

            params = req.get("params") or {}
            latency_ms = int((time.perf_counter() - entry["t_start"]) * 1000)
            status = "error" if "error" in resp else "success"

            records.append({
                "id": uuid.uuid4().hex,
                "session_id": session_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "direction": "response",
                "tool_name": params.get("name") or "tools/call",
                "input": json.dumps(params),
                "output": json.dumps(resp),
                "latency_ms": latency_ms,
                "status": status,
                "flags": "[]",
            })

        return records
