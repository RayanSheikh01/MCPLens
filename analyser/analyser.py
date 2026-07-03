def analyse(call, history, tool_schema) -> list[str]:
    """
    Analyse a JSON-RPC call and return a list of issues found.
    """
    issues = []

    # Check if the tool is known
    tool_name = call.get("tool_name")
    if tool_name not in tool_schema:
        issues.append(f"Unknown tool: {tool_name}")
        return issues

    # Check for required fields in the call
    required_fields = ["id", "session_id", "ts", "direction", "input", "output"]
    for field in required_fields:
        if field not in call:
            issues.append(f"Missing required field: {field}")

    # Check for latency issues
    latency_ms = call.get("latency_ms")
    if latency_ms is not None and latency_ms > 1000:
        issues.append(f"High latency: {latency_ms} ms")

    # Check for status issues
    status = call.get("status")
    if status not in ["success", "error"]:
        issues.append(f"Unknown status: {status}")

    # Check for flags
    flags = call.get("flags", "")
    if "deprecated" in flags:
        issues.append("Call uses deprecated features")

    # Additional checks can be added here based on tool_schema and history

    return issues


