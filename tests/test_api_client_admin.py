import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.client import KasmAPIClient

API_URL = "https://kasm.example.com"


@pytest.fixture
async def client():
    c = KasmAPIClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_create_user_sends_expected_fields(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/create_user", payload={"user": {"user_id": "u1"}})
        result = await client.create_user(username="bob", password="pw", first_name="Bob", last_name="X")
    assert result["user"]["user_id"] == "u1"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/create_user"))][0].kwargs["json"]
    assert sent["target_user"]["username"] == "bob"
    assert sent["target_user"]["password"] == "pw"


@pytest.mark.asyncio
async def test_get_user_by_id(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_user", payload={"user": {"user_id": "u1"}})
        result = await client.get_user(user_id="u1")
    assert result["user"]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_add_user_to_group_and_remove(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/add_user_group", payload={})
        m.post(f"{API_URL}/api/public/remove_user_group", payload={})
        await client.add_user_to_group(user_id="u1", group_id="g1")
        await client.remove_user_from_group(user_id="u1", group_id="g1")
