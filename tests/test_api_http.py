import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kasm_mcp.api.http import KasmAPIError, request_binary, request_json

API_URL = "https://kasm.example.com"


@pytest.mark.asyncio
async def test_request_json_success_injects_auth_and_returns_body():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"kasm": {"operational_status": "running"}})

    async with aiohttp.ClientSession() as session:
        with patch.object(session, 'request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            result = await request_json(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_status", {"kasm_id": "abc"}
            )
        assert result == {"kasm": {"operational_status": "running"}}
        # Verify the request was called with the correct auth fields
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        sent = call_args.kwargs["json"]
        assert sent["api_key"] == "key"
        assert sent["api_key_secret"] == "secret"
        assert sent["kasm_id"] == "abc"


@pytest.mark.asyncio
async def test_request_json_raises_on_error_status():
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(return_value={"error_message": "no resources"})

    async with aiohttp.ClientSession() as session:
        with patch.object(session, 'request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_json_raises_on_error_message_even_with_200():
    # Kasm sometimes returns HTTP 200 with an error_message body (observed live
    # for "No resources are available to create the requested Kasm").
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"error_message": "no resources"})

    async with aiohttp.ClientSession() as session:
        with patch.object(session, 'request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_binary_returns_raw_bytes():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"content-type": "image/jpeg"}
    mock_response.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0fakejpeg")

    async with aiohttp.ClientSession() as session:
        with patch.object(session, 'request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            result = await request_binary(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {"kasm_id": "abc"}
            )
        assert result == b"\xff\xd8\xff\xe0fakejpeg"


@pytest.mark.asyncio
async def test_request_binary_raises_on_json_error_body():
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json = AsyncMock(return_value={"error_message": "bad kasm_id"})

    async with aiohttp.ClientSession() as session:
        with patch.object(session, 'request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            with pytest.raises(KasmAPIError, match="bad kasm_id"):
                await request_binary(
                    session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {}
                )
