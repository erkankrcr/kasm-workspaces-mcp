from unittest.mock import AsyncMock

import pytest

from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.server import (
    create_kasm_session_logic,
    destroy_kasm_session_logic,
    execute_kasm_command_logic,
    get_session_screenshot_logic,
    get_session_status_logic,
    get_share_link_logic,
    list_user_sessions_logic,
)


def make_config(**overrides) -> KasmConfig:
    base = {
        "api_url": "https://kasm.example.com",
        "api_key": "key",
        "api_secret": "secret",
        "user_id": "user1",
        "allowed_roots": ["/home/kasm-user"],
        "admin_mode": False,
        "unofficial_api": False,
        "ssh_enabled": False,
        "ssh_key_path": None,
        "ssh_user": "kasm-user",
        "ssh_host_override": None,
    }
    base.update(overrides)
    return KasmConfig(**base)


@pytest.mark.asyncio
async def test_create_kasm_session_logic_success():
    client = AsyncMock()
    client.request_kasm.return_value = {"kasm_id": "abc", "kasm_url": "/#/connect/kasm/abc", "share_id": None, "status": "starting"}
    result = await create_kasm_session_logic(client, make_config(), image_name="img", group_id="grp")
    assert result == {
        "success": True,
        "kasm_id": "abc",
        "session_url": "/#/connect/kasm/abc",
        "share_id": None,
        "status": "starting",
    }
    client.request_kasm.assert_awaited_once_with(image_name="img", user_id="user1", group_id="grp", enable_sharing=False)


@pytest.mark.asyncio
async def test_create_kasm_session_logic_api_error_returns_success_false():
    client = AsyncMock()
    client.request_kasm.side_effect = KasmAPIError("no resources")
    result = await create_kasm_session_logic(client, make_config(), image_name="img", group_id="grp")
    assert result == {"success": False, "error": "no resources"}


@pytest.mark.asyncio
async def test_destroy_kasm_session_logic_success():
    client = AsyncMock()
    client.destroy_kasm.return_value = {}
    result = await destroy_kasm_session_logic(client, make_config(), kasm_id="abc")
    assert result == {"success": True, "kasm_id": "abc"}
    client.destroy_kasm.assert_awaited_once_with(kasm_id="abc", user_id="user1")


@pytest.mark.asyncio
async def test_get_session_status_logic_success():
    client = AsyncMock()
    client.get_kasm_status.return_value = {"kasm": {"operational_status": "running"}}
    result = await get_session_status_logic(client, make_config(), kasm_id="abc")
    assert result == {"success": True, "kasm_id": "abc", "status": {"operational_status": "running"}}


@pytest.mark.asyncio
async def test_list_user_sessions_logic_success():
    client = AsyncMock()
    client.get_user_kasms.return_value = {"kasms": [{"kasm_id": "abc"}]}
    result = await list_user_sessions_logic(client, make_config())
    assert result == {"success": True, "sessions": [{"kasm_id": "abc"}]}


@pytest.mark.asyncio
async def test_get_share_link_logic_returns_url_with_view_only_note():
    client = AsyncMock()
    client.join_kasm.return_value = {"kasm_url": "/#/connect/join/abc/anon/token"}
    result = await get_share_link_logic(client, make_config(), share_id="abc")
    assert result["success"] is True
    assert result["share_url"] == "/#/connect/join/abc/anon/token"
    assert "view-only" in result["note"].lower()


@pytest.mark.asyncio
async def test_get_session_screenshot_logic_saves_to_file(tmp_path):
    client = AsyncMock()
    client.get_kasm_screenshot.return_value = b"\xff\xd8\xff\xe0fake"
    dest = tmp_path / "shot.jpg"
    result = await get_session_screenshot_logic(client, make_config(), kasm_id="abc", save_to_file=str(dest))
    assert result == {"success": True, "kasm_id": "abc", "file_path": str(dest)}
    assert dest.read_bytes() == b"\xff\xd8\xff\xe0fake"


@pytest.mark.asyncio
async def test_get_session_screenshot_logic_returns_base64_without_save_path():
    import base64

    client = AsyncMock()
    client.get_kasm_screenshot.return_value = b"\xff\xd8\xff\xe0fake"
    result = await get_session_screenshot_logic(client, make_config(), kasm_id="abc")
    assert result["success"] is True
    assert base64.b64decode(result["screenshot_base64"]) == b"\xff\xd8\xff\xe0fake"


@pytest.mark.asyncio
async def test_execute_kasm_command_logic_rejects_dangerous_command_without_calling_api():
    client = AsyncMock()
    result = await execute_kasm_command_logic(client, make_config(), kasm_id="abc", command="ls; rm -rf /")
    assert result["success"] is False
    assert result["error_type"] == "security"
    client.exec_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_kasm_command_logic_dispatches_and_is_honest_about_output():
    client = AsyncMock()
    client.exec_command.return_value = None
    result = await execute_kasm_command_logic(client, make_config(), kasm_id="abc", command="whoami", user="kasm-user")
    assert result["success"] is True
    assert result["dispatched"] is True
    assert "output" not in result
    assert "exit_code" not in result
    client.exec_command.assert_awaited_once_with(
        kasm_id="abc", user_id="user1", command="whoami", working_dir=None, user="kasm-user"
    )
