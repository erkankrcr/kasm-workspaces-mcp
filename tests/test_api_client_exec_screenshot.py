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
async def test_get_kasm_screenshot_returns_raw_bytes_not_json(client):
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            body=b"\xff\xd8\xff\xe0fakejpeg",
            content_type="image/jpeg",
        )
        result = await client.get_kasm_screenshot(kasm_id="abc", user_id="user1", width=1600, height=900)
    assert result == b"\xff\xd8\xff\xe0fakejpeg"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/get_kasm_screenshot"))][0].kwargs["json"]
    assert sent["width"] == 1600
    assert sent["height"] == 900


@pytest.mark.asyncio
async def test_exec_command_returns_none_it_never_carries_output(client):
    # exec_command_kasm is fire-and-forget on the real API: no stdout/exit_code
    # field exists to return, so this method's contract is "dispatched or raised",
    # never a fabricated result.
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/exec_command_kasm", payload={"kasm": {}, "current_time": "now"})
        result = await client.exec_command(kasm_id="abc", user_id="user1", command="whoami", user="kasm-user")
    assert result is None
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/exec_command_kasm"))][0].kwargs["json"]
    assert sent["exec_config"]["cmd"] == "whoami"
    assert sent["exec_config"]["user"] == "kasm-user"


@pytest.mark.asyncio
async def test_join_kasm_without_user_id_omits_field(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/join_kasm", payload={"kasm_url": "/#/connect/join/abc/anon/token"})
        result = await client.join_kasm(share_id="abc")
    assert result["kasm_url"] == "/#/connect/join/abc/anon/token"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/join_kasm"))][0].kwargs["json"]
    assert "user_id" not in sent


@pytest.mark.asyncio
async def test_get_images_returns_payload(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_images", payload={"images": [{"image_id": "abc", "friendly_name": "Chromium"}]})
        result = await client.get_images()
    assert result["images"][0]["friendly_name"] == "Chromium"
