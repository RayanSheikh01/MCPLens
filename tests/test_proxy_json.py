

from tests.mock_mcp import mock_mcp_server

def test_proxy_jsonrpc_capture_and_ws_push(monkeypatch):
    import httpx2
    from fastapi.testclient import TestClient
    from proxy.proxy import app as proxy_app

    # use mock mcp server
    def handler(request):
        if request.url.path == "/test_path":
            return httpx2.Response(200, json=mock_mcp_server["test_path"])
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handler)
    real_init = httpx2.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx2.AsyncClient, "__init__", patched_init)

    call = {"jsonrpc": "2.0", "method": "test_method", "id": 1}

    with TestClient(proxy_app) as proxy_client:
        # Connect the WS client first so it is registered before the call is captured.
        with proxy_client.websocket_connect("/ws") as websocket:
            response = proxy_client.post("/mcp/test_server/test_path", json=call)

            assert response.status_code == 200
            assert response.json() == {"jsonrpc": "2.0", "result": "success", "id": 1}

            # The proxy captures the forwarded JSON-RPC call and pushes it to WS clients.
            assert websocket.receive_json() == call
