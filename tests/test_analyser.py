import pytest

from analyser.analyser import analyse



def test_analyse():
    call = {
        "id": 1,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 500,
        "status": "success",
        "flags": "",
        "tool_name": "test_tool"
    }
    history = []
    tool_schema = {"test_tool": {"description": "A test tool"}}

    issues = analyse(call, history, tool_schema)
    assert issues == []
    
def test_analyse_with_issues():
    call = {
        "id": 2,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 1500,  # High latency
        "status": "unknown_status",  # Unknown status
        "flags": "deprecated",  # Deprecated feature
        "tool_name": "test_tool"
    }
    history = []
    tool_schema = {"test_tool": {"description": "A test tool"}}

    issues = analyse(call, history, tool_schema)
    assert len(issues) == 3
    assert "High latency" in issues[0]
    assert "Unknown status" in issues[1]
    assert "deprecated" in issues[2]
    
def test_analyse_missing_fields():
    call = {
        "id": 3,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        # Missing 'input' and 'output'
        "latency_ms": 500,
        "status": "success",
        "flags": "",
        "tool_name": "test_tool"
    }
    history = []
    tool_schema = {"test_tool": {"description": "A test tool"}}

    issues = analyse(call, history, tool_schema)
    assert len(issues) == 2
    assert "Missing required field: input" in issues
    assert "Missing required field: output" in issues
    
def test_analyse_unknown_tool():
    call = {
        "id": 4,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 500,
        "status": "success",
        "flags": ""
    }
    history = []
    tool_schema = {}  # No known tools

    issues = analyse(call, history, tool_schema)
    assert len(issues) == 1
    assert "Unknown tool" in issues[0]
    
def test_analyse_with_history():
    call = {
        "id": 5,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 500,
        "status": "success",
        "flags": "",
        "tool_name": "test_tool"
    }
    history = [
        {
            "id": 4,
            "session_id": "test_session",
            "ts": 1234567880,
            "direction": "request",
            "input": {"param1": "value1"},
            "output": {"result": 18},
            "latency_ms": 400,
            "status": "success",
            "flags": ""
        }
    ]
    tool_schema = {"test_tool": {"description": "A test tool"}}

    issues = analyse(call, history, tool_schema)
    assert issues == []
    
def test_analyse_with_additional_checks():
    call = {
        "id": 6,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 500,
        "status": "success",
        "flags": "",
        "tool_name": "test_tool"
    }
    history = []
    tool_schema = {
        "test_tool": {
            "description": "A test tool",
            "additional_check": lambda call: call["latency_ms"] < 1000
        }
    }

    issues = analyse(call, history, tool_schema)
    assert issues == []
    
def test_analyse_with_additional_checks_failure():
    call = {
        "id": 7,
        "session_id": "test_session",
        "ts": 1234567890,
        "direction": "request",
        "input": {"param1": "value1"},
        "output": {"result": 19},
        "latency_ms": 1500,  # High latency
        "status": "success",
        "flags": "",
        "tool_name": "test_tool"
    }
    history = []
    tool_schema = {
        "test_tool": {
            "description": "A test tool",
            "additional_check": lambda call: call["latency_ms"] < 1000
        }
    }

    issues = analyse(call, history, tool_schema)
    assert len(issues) == 1
    assert "High latency" in issues[0]

