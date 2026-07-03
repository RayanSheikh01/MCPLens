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
