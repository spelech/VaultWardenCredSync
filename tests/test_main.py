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
            response = await ac.get("/api/health")
        assert response.status_code == 403
