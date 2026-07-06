import json

import fastapi
import httpx2

from proxy.hub import Hub

app = fastapi.FastAPI()
hub = Hub()

@app.api_route("/mcp/{server}/{path:path}", methods=["GET", "POST", "DELETE"])
async def forward(server, path, request: fastapi.Request):
    """
    Forward the request to the specified server and path, capturing the
    JSON-RPC call and broadcasting it to connected WebSocket clients.
    """
    url = f"http://{server}/{path}"
    headers = dict(request.headers)
    method = request.method
    body = await request.body()

    # Capture the outgoing JSON-RPC call.
    try:
        await hub.broadcast(json.loads(body))
    except (json.JSONDecodeError, ValueError):
        pass

    client = httpx2.AsyncClient()
    req = client.build_request(method, url, headers=headers, content=body)
    response = await client.send(req, stream=True)
    content_type = response.headers.get("content-type", "")

    if content_type.startswith("text/event-stream"):
        # Stream the SSE response back while teeing each chunk into an SSE
        # parser, broadcasting captured JSON-RPC messages to WebSocket clients.
        async def event_stream():
            buffer = ""
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    buffer += chunk.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        try:
                            await hub.broadcast(json.loads(data))
                        except (json.JSONDecodeError, ValueError):
                            pass
            finally:
                await response.aclose()
                await client.aclose()

        return fastapi.responses.StreamingResponse(
            event_stream(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="text/event-stream",
        )

    content = await response.aread()
    await response.aclose()
    await client.aclose()
    return fastapi.Response(content=content, status_code=response.status_code, headers=dict(response.headers))

@app.websocket("/ws")
async def websocket_endpoint(websocket: fastapi.WebSocket):
    """
    Register queue, stream captured calls
    """
    await websocket.accept()
    queue = hub.register()
    try:
        while True:
            call = await queue.get()
            await websocket.send_json(call)
    except fastapi.WebSocketDisconnect:
        pass
    finally:
        hub.unregister(queue)


@app.get("/")
async def root():
    return fastapi.responses.FileResponse("dashboard/index.html")
