def iter_sse_messages(chunk_stream):
    """
    Iterate over SSE messages from a chunk stream.
    """
    buffer = ""
    for chunk in chunk_stream:
        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            yield data
