import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.http import KasmAPIError, request_binary, request_json

API_URL = "https://kasm.example.com"


@pytest.mark.asyncio
async def test_request_json_success_injects_auth_and_returns_body():
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_kasm_status", payload={"kasm": {"operational_status": "running"}})
        async with aiohttp.ClientSession() as session:
            result = await request_json(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_status", {"kasm_id": "abc"}
            )
        assert result == {"kasm": {"operational_status": "running"}}
        request = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/get_kasm_status"))][0]
        sent = request.kwargs["json"]
        assert sent["api_key"] == "key"
        assert sent["api_key_secret"] == "secret"
        assert sent["kasm_id"] == "abc"


@pytest.mark.asyncio
async def test_request_json_raises_on_error_status():
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", status=400, payload={"error_message": "no resources"})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_json_raises_on_error_message_even_with_200():
    # Kasm sometimes returns HTTP 200 with an error_message body (observed live
    # for "No resources are available to create the requested Kasm").
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", status=200, payload={"error_message": "no resources"})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_json_succeeds_with_empty_error_message_field():
    # Some Kasm responses carry an "error_message" key that's just an empty
    # string (no actual error) alongside real data; presence of the key alone
    # must not trigger a failure.
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_kasms", status=200, payload={"kasms": [], "error_message": ""})
        async with aiohttp.ClientSession() as session:
            result = await request_json(session, API_URL, "key", "secret", "POST", "/api/public/get_kasms", {})
        assert result == {"kasms": [], "error_message": ""}


@pytest.mark.asyncio
async def test_request_json_wraps_connection_failure_as_kasm_api_error():
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", exception=aiohttp.ClientConnectionError("boom"))
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_binary_returns_raw_bytes():
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            body=b"\xff\xd8\xff\xe0fakejpeg",
            content_type="image/jpeg",
        )
        async with aiohttp.ClientSession() as session:
            result = await request_binary(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {"kasm_id": "abc"}
            )
        assert result == b"\xff\xd8\xff\xe0fakejpeg"


@pytest.mark.asyncio
async def test_request_binary_raises_on_json_error_body():
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            status=400,
            payload={"error_message": "bad kasm_id"},
        )
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="bad kasm_id"):
                await request_binary(
                    session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {}
                )
