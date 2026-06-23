import pytest
import httpx
from unittest.mock import patch
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    with patch("app.main.is_setup_complete", return_value=True):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_setup_redirect():
    with patch("app.main.is_setup_complete", return_value=False):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            # Assuming setup is not complete in test env
            response = await ac.get("/")
        assert response.status_code == 307
        assert response.headers["location"] == "/setup"

@pytest.mark.asyncio
async def test_api_setup_blocked():
    with patch("app.main.is_setup_complete", return_value=False):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            # Use a restricted endpoint instead of /api/health
            response = await ac.get("/api/litellm/keys")
        assert response.status_code == 403

@pytest.mark.asyncio
async def test_api_push_ssh():
    with patch("app.main.is_setup_complete", return_value=True), \
         patch("app.main.get_secret", return_value="mock-session-id"), \
         patch("app.main.push_ssh_key_to_host") as mock_push, \
         patch("app.main.add_registered_host_to_ssh_key") as mock_track:
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            cookies = {"portal_session": "mock-session-id"}
            payload = {
                "host": "192.168.1.100",
                "username": "root",
                "public_key": "ssh-ed25519 AAAAC3...",
                "password": "mypassword",
                "port": 22,
                "name": "my-ssh-key"
            }
            response = await ac.post("/api/push-ssh", json=payload, cookies=cookies)
            
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_push.assert_called_once_with(
            host="192.168.1.100",
            username="root",
            public_key="ssh-ed25519 AAAAC3...",
            password="mypassword",
            port=22
        )
        mock_track.assert_called_once_with("my-ssh-key", "192.168.1.100")

@pytest.mark.asyncio
async def test_api_get_ssh_key_details():
    mock_key = {
        "name": "test-key",
        "private_key": "private...",
        "public_key": "public...",
        "fingerprint": "fingerprint...",
        "registered_hosts": "1.1.1.1"
    }
    with patch("app.main.is_setup_complete", return_value=True), \
         patch("app.main.get_secret", return_value="mock-session-id"), \
         patch("app.main.get_ssh_key_item", return_value=mock_key) as mock_get:
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            cookies = {"portal_session": "mock-session-id"}
            response = await ac.get("/api/vaultwarden/ssh-keys/test-key", cookies=cookies)
            
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["key"] == mock_key
        mock_get.assert_called_once_with("test-key")


