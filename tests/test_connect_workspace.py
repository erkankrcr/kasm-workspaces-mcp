from unittest.mock import AsyncMock

import pytest

from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.registry.db import connect, get_workspace_state
from kasm_mcp.server import connect_workspace_logic

KALI_IMAGE = {"image_id": "kali-id", "name": "kasmweb/kali-rolling:1.0", "friendly_name": "Kali Linux", "description": "Pentest distro."}


def make_config(**overrides) -> KasmConfig:
    base = {
        "api_url": "https://kasm.example.com", "api_key": "key", "api_secret": "secret", "user_id": "user1",
        "allowed_roots": ["/home/kasm-user"], "admin_mode": False, "unofficial_api": False,
        "ssh_enabled": False, "ssh_key_path": None, "ssh_user": "kasm-user", "ssh_host_override": None,
        "workspace_registry_enabled": True, "db_path": "/tmp/test-registry.db",
    }
    base.update(overrides)
    return KasmConfig(**base)


@pytest.fixture
def db(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    yield conn
    conn.close()


@pytest.mark.asyncio
async def test_connect_workspace_creates_new_session_and_persists_state(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}
    client.request_kasm.return_value = {"kasm_id": "new-kasm-id", "status": "starting"}

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali", group_id="grp1")

    assert result["success"] is True
    assert result["kasm_id"] == "new-kasm-id"
    assert result["image_id"] == "kali-id"
    assert result["reused_session"] is False
    client.request_kasm.assert_awaited_once_with(image_id="kali-id", user_id="user1", group_id="grp1")
    assert get_workspace_state(db, "kali-id") == {"image_id": "kali-id", "last_group_id": "grp1", "last_kasm_id": "new-kasm-id"}


@pytest.mark.asyncio
async def test_connect_workspace_reuses_running_session_without_creating_new_one(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}
    client.get_kasm_status.return_value = {"kasm": {"operational_status": "running"}}
    from kasm_mcp.registry.db import upsert_workspace_state
    upsert_workspace_state(db, image_id="kali-id", group_id="grp1", kasm_id="old-kasm-id")

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali")

    assert result["success"] is True
    assert result["kasm_id"] == "old-kasm-id"
    assert result["reused_session"] is True
    client.request_kasm.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_workspace_creates_new_session_when_previous_one_not_running(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}
    client.get_kasm_status.return_value = {"kasm": {"operational_status": "stopped"}}
    client.request_kasm.return_value = {"kasm_id": "fresh-kasm-id", "status": "starting"}
    from kasm_mcp.registry.db import upsert_workspace_state
    upsert_workspace_state(db, image_id="kali-id", group_id="grp1", kasm_id="old-kasm-id")

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali")

    assert result["success"] is True
    assert result["kasm_id"] == "fresh-kasm-id"
    assert result["reused_session"] is False
    client.request_kasm.assert_awaited_once_with(image_id="kali-id", user_id="user1", group_id="grp1")


@pytest.mark.asyncio
async def test_connect_workspace_returns_bootstrap_error_when_no_group_id_and_no_state(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali")

    assert result["success"] is False
    assert result["error_type"] == "bootstrap_required"
    client.request_kasm.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_workspace_unresolved_image_returns_candidates(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}

    result = await connect_workspace_logic(client, make_config(), db, identifier="nonexistent", group_id="grp1")

    assert result["success"] is False
    assert result["candidates"] == []
    client.request_kasm.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_workspace_dispatches_command_after_connecting(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}
    client.request_kasm.return_value = {"kasm_id": "new-kasm-id", "status": "starting"}
    client.exec_command.return_value = None

    result = await connect_workspace_logic(
        client, make_config(), db, identifier="kali", group_id="grp1", command="whoami"
    )

    assert result["success"] is True
    assert result["command_result"]["success"] is True
    assert result["command_result"]["dispatched"] is True
    client.exec_command.assert_awaited_once_with(
        kasm_id="new-kasm-id", user_id="user1", command="whoami", working_dir=None, user=None
    )


@pytest.mark.asyncio
async def test_connect_workspace_request_kasm_response_missing_kasm_id_returns_success_false(db):
    client = AsyncMock()
    client.get_images.return_value = {"images": [KALI_IMAGE]}
    client.request_kasm.return_value = {"status": "starting"}

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali", group_id="grp1")

    assert result == {"success": False, "error": "Kasm API returned no kasm_id from request_kasm."}


@pytest.mark.asyncio
async def test_connect_workspace_get_images_api_error_returns_success_false(db):
    client = AsyncMock()
    client.get_images.side_effect = KasmAPIError("down")

    result = await connect_workspace_logic(client, make_config(), db, identifier="kali", group_id="grp1")

    assert result == {"success": False, "error": "down"}
