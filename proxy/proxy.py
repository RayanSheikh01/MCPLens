import json

import fastapi
import httpx

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

    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, content=body)

    try:
        await hub.broadcast(json.loads(body))
    except (json.JSONDecodeError, ValueError):
        pass

    return fastapi.Response(content=response.content, status_code=response.status_code, headers=dict(response.headers))

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
