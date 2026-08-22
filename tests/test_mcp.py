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
