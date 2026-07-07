import pytest

#  parse batched array, pair request↔response by id, compute latency

def test_parse_jsonrpc():
    from proxy.interceptor import parse_jsonrpc

    # Test single request
    raw_single = '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}'
    result_single = parse_jsonrpc(raw_single)
    assert isinstance(result_single, list)
    assert len(result_single) == 1
    assert result_single[0]['id'] == 1

    # Test batch request
    raw_batch = '[{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}, {"jsonrpc": "2.0", "method": "add", "params": [1, 2], "id": 2}]'
    result_batch = parse_jsonrpc(raw_batch)
    assert isinstance(result_batch, list)
    assert len(result_batch) == 2
    assert result_batch[0]['id'] == 1
    assert result_batch[1]['id'] == 2

    # Test invalid JSON
    raw_invalid = 'invalid json'
    result_invalid = parse_jsonrpc(raw_invalid)
    assert result_invalid == []


def test_pairer_pairs_toolscall():
    from proxy.interceptor import Pairer

    pairer = Pairer()
    ctx = {"session_id": "sess-1"}
    req = {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
           "params": {"name": "send_email", "arguments": {"to": "a@b.com"}}}
    resp = {"jsonrpc": "2.0", "id": 9, "result": {"content": []}}

    pairer.on_request(req, ctx)
    records = pairer.on_response(resp, ctx)

    assert len(records) == 1
    rec = records[0]
    assert rec["session_id"] == "sess-1"
    assert rec["tool_name"] == "send_email"
    assert rec["status"] == "success"
    assert rec["latency_ms"] >= 0


def test_pairer_ignores_non_toolscall():
    from proxy.interceptor import Pairer

    pairer = Pairer()
    req = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    resp = {"jsonrpc": "2.0", "id": 1, "result": "pong"}
    pairer.on_request(req, {})
    assert pairer.on_response(resp, {}) == []


def test_pairer_error_status():
    from proxy.interceptor import Pairer

    pairer = Pairer()
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
           "params": {"name": "x"}}
    resp = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "boom"}}
    pairer.on_request(req, {})
    records = pairer.on_response(resp, {})
    assert records[0]["status"] == "error"
