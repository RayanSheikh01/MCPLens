import re

# Output text matching any of these suggests a prompt-injection payload.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|previous\s+|prior\s+|the\s+)*instructions",
    r"disregard\s+(the\s+|all\s+)*(above|previous)",
    r"system prompt",
    r"you are now",
    r"<\s*/?\s*system\s*>",
]

# Output text matching any of these suggests sensitive-data exfiltration.
EXFIL_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",          # email
    r"\b(sk|pk|api|key|token|secret)[-_][A-Za-z0-9]{16,}\b",     # api key/token
    r"\b(?:\d[ -]*?){13,16}\b",                                  # credit card
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",                       # private key
]


def _output_text(call) -> str:
    """Return the call output coerced to text (output may be dict or JSON str)."""
    output = call.get("output", "")
    return output if isinstance(output, str) else str(output)


def _security_flags(call, history) -> list[str]:
    """Plan-spec security/quality flags layered on top of the base checks."""
    flags = []

    latency_ms = call.get("latency_ms")
    if latency_ms is not None and latency_ms > 2000:
        flags.append(f"SLOW_CALL: {latency_ms} ms")

    # REPEATED_FAILURE: the last 3 calls to the same tool all errored.
    tool_name = call.get("tool_name")
    if tool_name is not None:
        same_tool = [c for c in history if c.get("tool_name") == tool_name]
        recent = same_tool[-3:]
        if len(recent) == 3 and all(c.get("status") == "error" for c in recent):
            flags.append(f"REPEATED_FAILURE: {tool_name}")

    text = _output_text(call)
    if any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS):
        flags.append("POSSIBLE_INJECTION")
    if any(re.search(p, text) for p in EXFIL_PATTERNS):
        flags.append("DATA_EXFIL")

    return flags


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

    # Security / quality flags (SLOW_CALL, REPEATED_FAILURE, POSSIBLE_INJECTION,
    # DATA_EXFIL) layered on top of the base validation checks.
    issues.extend(_security_flags(call, history))

    return issues


