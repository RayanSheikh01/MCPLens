import pytest

# mock emits event-stream; assert client gets bytes unbuffered + capture fires

def test_proxy_sse_capture_and_ws_push(monkeypatch):
    import httpx2
    from fastapi.testclient import TestClient
    from proxy.proxy import app as proxy_app

    # use mock mcp server
    def handler(request):
        if request.url.path == "/sse_path":
            # Simulate an SSE response with two messages.
            sse_content = (
                "data: {\"jsonrpc\": \"2.0\", \"method\": \"event1\", \"id\": 1}\n\n"
                "data: {\"jsonrpc\": \"2.0\", \"method\": \"event2\", \"id\": 2}\n\n"
            )
            return httpx2.Response(
                200,
                content=sse_content.encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handler)
    real_init = httpx2.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx2.AsyncClient, "__init__", patched_init)

    with TestClient(proxy_app) as proxy_client:
        # Connect the WS client first so it is registered before the SSE stream is captured.
        with proxy_client.websocket_connect("/ws") as websocket:
            response = proxy_client.get("/mcp/test_server/sse_path")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"

            # The proxy captures the forwarded SSE messages and pushes them to WS clients.
            assert websocket.receive_json() == {"jsonrpc": "2.0", "method": "event1", "id": 1}
            assert websocket.receive_json() == {"jsonrpc": "2.0", "method": "event2", "id": 2}