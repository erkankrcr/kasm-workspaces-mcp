from unittest.mock import AsyncMock

import pytest

from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.server import build_server, diagnose_permissions_logic


def make_config(**overrides) -> KasmConfig:
    base = {
        "api_url": "https://kasm.example.com", "api_key": "key", "api_secret": "secret", "user_id": "user1",
        "allowed_roots": ["/home/kasm-user"], "admin_mode": False, "unofficial_api": False,
        "ssh_enabled": False, "ssh_key_path": None, "ssh_user": "kasm-user", "ssh_host_override": None,
        "workspace_registry_enabled": False, "db_path": "/tmp/test-registry.db",
    }
    base.update(overrides)
    return KasmConfig(**base)


def make_all_ok_client() -> AsyncMock:
    client = AsyncMock()
    client.get_images.return_value = {"images": []}
    client.get_kasms.return_value = {"kasms": []}
    client.get_user.return_value = {"user": {}}
    client.get_kasm_status.return_value = {"kasm": {}}
    client.exec_command.return_value = None
    return client


@pytest.mark.asyncio
async def test_diagnose_permissions_all_ok_when_every_call_succeeds():
    client = make_all_ok_client()
    result = await diagnose_permissions_logic(client, make_config())
    assert result["all_ok"] is True
    assert result["missing_permissions"] == []
    assert all(check["status"] == "ok" for check in result["checks"].values())


@pytest.mark.asyncio
async def test_diagnose_permissions_treats_non_auth_error_as_permission_present():
    client = make_all_ok_client()
    client.get_kasm_status.side_effect = KasmAPIError("Invalid kasm_id (00000000-0000-0000-0000-000000000000)")
    result = await diagnose_permissions_logic(client, make_config())
    assert result["all_ok"] is True
    assert result["checks"]["User + Users Auth Session"]["status"] == "ok"


@pytest.mark.asyncio
async def test_diagnose_permissions_detects_missing_users_auth_session():
    client = make_all_ok_client()
    client.get_kasm_status.side_effect = KasmAPIError("Unauthorized")
    result = await diagnose_permissions_logic(client, make_config())
    assert result["all_ok"] is False
    assert "User + Users Auth Session" in result["missing_permissions"]
    assert result["checks"]["User + Users Auth Session"]["status"] == "missing"


@pytest.mark.asyncio
async def test_diagnose_permissions_detects_missing_sessions_modify():
    client = make_all_ok_client()
    client.exec_command.side_effect = KasmAPIError("Unauthorized")
    result = await diagnose_permissions_logic(client, make_config())
    assert result["all_ok"] is False
    assert "Sessions Modify" in result["missing_permissions"]


@pytest.mark.asyncio
async def test_diagnose_permissions_detects_missing_images_view_and_sessions_view_and_users_view():
    client = make_all_ok_client()
    client.get_images.side_effect = KasmAPIError("Unauthorized")
    client.get_kasms.side_effect = KasmAPIError("Unauthorized")
    client.get_user.side_effect = KasmAPIError("Unauthorized")
    result = await diagnose_permissions_logic(client, make_config())
    assert set(result["missing_permissions"]) == {"Images View", "Sessions View", "Users View"}


@pytest.mark.asyncio
async def test_diagnose_permissions_result_includes_fix_pointer_to_docs():
    client = make_all_ok_client()
    result = await diagnose_permissions_logic(client, make_config())
    assert "API_BEHAVIOR.md" in result["note"]


def test_diagnose_permissions_tool_registered_by_default_without_any_flag():
    server = build_server(AsyncMock(), make_config())
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "diagnose_permissions" in names
