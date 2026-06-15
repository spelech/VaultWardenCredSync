import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_setup_redirect():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Assuming setup is not complete in test env
        response = await ac.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/setup"
