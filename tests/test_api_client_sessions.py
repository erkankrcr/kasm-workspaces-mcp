import json
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.api.http import KasmAPIError

API_URL = "https://kasm.example.com"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
async def client():
    c = KasmAPIClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_request_kasm_without_sharing_omits_enable_sharing_field(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", payload={"kasm_id": "abc", "kasm_url": "/#/connect/kasm/abc", "share_id": None, "status": "starting"})
        result = await client.request_kasm(image_id="img123", user_id="user1", group_id="group1")
    assert result["kasm_id"] == "abc"
    assert result["share_id"] is None
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/request_kasm"))][0].kwargs["json"]
    assert "enable_sharing" not in sent
    assert sent["image_id"] == "img123"
    assert sent["group_id"] == "group1"


@pytest.mark.asyncio
async def test_request_kasm_with_sharing_sets_enable_sharing_true(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", payload={"kasm_id": "abc", "share_id": "c20d04e8", "status": "starting"})
        result = await client.request_kasm(image_id="img123", user_id="user1", group_id="group1", enable_sharing=True)
    assert result["share_id"] == "c20d04e8"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/request_kasm"))][0].kwargs["json"]
    assert sent["enable_sharing"] is True


@pytest.mark.asyncio
async def test_get_kasm_status_returns_full_fixture_shape(client):
    fixture = json.loads((FIXTURES / "get_kasm_status_response.json").read_text())
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_kasm_status", payload=fixture)
        result = await client.get_kasm_status(kasm_id="b057c375...", user_id="user1")
    assert result["kasm"]["operational_status"] == "running"
    assert result["kasm"]["share_id"] is None


@pytest.mark.asyncio
async def test_destroy_kasm_raises_kasm_api_error_on_failure(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/destroy_kasm", status=400, payload={"error_message": "not found"})
        with pytest.raises(KasmAPIError, match="not found"):
            await client.destroy_kasm(kasm_id="missing", user_id="user1")


@pytest.mark.asyncio
async def test_get_user_kasms_and_get_kasms_and_pause_resume(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_user_kasms", payload={"kasms": []})
        m.post(f"{API_URL}/api/public/get_kasms", payload={"kasms": []})
        m.post(f"{API_URL}/api/public/pause_kasm", payload={"status": "paused"})
        m.post(f"{API_URL}/api/public/resume_kasm", payload={"status": "running"})
        assert await client.get_user_kasms(user_id="user1") == {"kasms": []}
        assert await client.get_kasms() == {"kasms": []}
        assert await client.pause_kasm(kasm_id="abc", user_id="user1") == {"status": "paused"}
        assert await client.resume_kasm(kasm_id="abc", user_id="user1") == {"status": "running"}
