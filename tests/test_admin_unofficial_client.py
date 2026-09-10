import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient

API_URL = "https://kasm.example.com"


@pytest.fixture
async def client():
    c = KasmUnofficialAdminClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_get_registries_hits_admin_path(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/get_registries", payload={"registries": []})
        result = await client.get_registries()
    assert result == {"registries": []}


@pytest.mark.asyncio
async def test_create_registry_sends_target_registry(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/create_registry", payload={"registry": {"registry_id": "r1"}})
        await client.create_registry(url="registry.example.com", username="u", password="p")
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/admin/create_registry"))][0].kwargs["json"]
    assert sent["target_registry"]["url"] == "registry.example.com"


@pytest.mark.asyncio
async def test_create_workspace_image_sends_target_image(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/create_image", payload={"image": {"image_id": "i1"}})
        await client.create_workspace_image(image_name="kasmweb/kali-rolling:1.0", friendly_name="Kali")
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/admin/create_image"))][0].kwargs["json"]
    assert sent["target_image"]["image_name"] == "kasmweb/kali-rolling:1.0"
    assert sent["target_image"]["friendly_name"] == "Kali"
