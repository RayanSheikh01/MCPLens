def parse_jsonrpc(raw) -> list[dict]:
    """
    Parse a raw JSON-RPC request or response and return a list of dictionaries representing the calls.
    """
    import json
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
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
    def on_request(self, msg, ctx):
        """
        Handle a JSON-RPC request message.
        """
        if not hasattr(self, "pending"):
            self.pending = {}

        calls = msg if isinstance(msg, (dict, list)) else parse_jsonrpc(msg)

        request_ids = []
        for call in calls:
            if not isinstance(call, dict):
                continue

            request_id = call.get("id")
            if request_id is None:
                continue

            self.pending[request_id] = call
            request_ids.append(request_id)

        if ctx is not None:
            try:
                ctx.setdefault("jsonrpc_request_ids", []).extend(request_ids)
            except AttributeError:
                pass

        return msg
        