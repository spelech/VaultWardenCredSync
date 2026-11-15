import json
import pytest
import httpx
from app.main import app

@pytest.mark.asyncio
async def test_mcp_unauthorized_without_token():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            },
            headers={"Accept": "application/json, text/event-stream"}
        )
    # Auth verification should trigger 401 Unauthorized with OAuth discovery header
    assert response.status_code == 401
    assert "www-authenticate" in response.headers

@pytest.mark.asyncio
async def test_mcp_server_metadata():
    from app.mcp_server import mcp
    assert mcp.name == "QuickCreds"

@pytest.mark.asyncio
async def test_mcp_gateway_api_key_no_redirect(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "test-gateway-key-123")
    headers = {
        "Authorization": "Bearer test-gateway-key-123",
        "Accept": "application/json, text/event-stream",
    }
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=False) as ac:
            init_resp = await ac.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0.0"}
                    }
                },
                headers=headers,
            )
            assert init_resp.status_code == 200
            sid = init_resp.headers.get("mcp-session-id")
            req_headers = dict(headers)
            if sid:
                req_headers["Mcp-Session-Id"] = sid
            await ac.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=req_headers)
            tools_resp = await ac.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=req_headers)
            assert tools_resp.status_code == 200
            raw = tools_resp.text
            for line in raw.splitlines():
                if line.startswith("data: "):
                    raw = line[6:]
                    break
            tool_names = [t["name"] for t in json.loads(raw)["result"]["tools"]]
            assert "create_and_sync_ssh_key" in tool_names
            assert "create_and_sync_litellm_key" in tool_names


@pytest.mark.asyncio
async def test_mcp_oauth_discovery_and_callback_routes():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://quickcreds.wileyriley.com",
        follow_redirects=False,
    ) as ac:
        prm = await ac.get("/.well-known/oauth-protected-resource/mcp")
        assert prm.status_code == 200
        assert prm.json()["resource"] == "https://quickcreds.wileyriley.com/mcp"

        asm = await ac.get("/.well-known/oauth-authorization-server")
        assert asm.status_code == 200
        assert asm.json()["authorization_endpoint"] == "https://quickcreds.wileyriley.com/authorize"

        cb = await ac.get("/mcp/auth/callback")
        assert cb.status_code == 400
