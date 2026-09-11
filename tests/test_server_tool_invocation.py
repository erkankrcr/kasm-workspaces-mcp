"""Round-trip tests that invoke tools through their actual registered MCP
closures (``server._tool_manager.get_tool(name).run(...)``) rather than
calling the *_logic functions directly.

This closes the gap that let the `**fields` bug (finding #1 of the final
whole-branch review) hide through 12 individual task reviews: every prior
tool-tier test only checked tool *names*/*descriptions* were registered,
never that a call through the real closure forwards arguments correctly.
"""

from unittest.mock import AsyncMock

import pytest

from kasm_mcp.config import KasmConfig
from kasm_mcp.server import build_server


def make_config(**overrides) -> KasmConfig:
    base = {
        "api_url": "https://kasm.example.com", "api_key": "key", "api_secret": "secret", "user_id": "user1",
        "allowed_roots": ["/home/kasm-user"], "admin_mode": False, "unofficial_api": False,
        "ssh_enabled": False, "ssh_key_path": None, "ssh_user": "kasm-user", "ssh_host_override": None,
        "workspace_registry_enabled": False,
        "db_path": "/tmp/test-registry.db",
    }
    base.update(overrides)
    return KasmConfig(**base)


@pytest.mark.asyncio
async def test_execute_kasm_command_ssh_tool_forwards_args_to_ssh_exec(monkeypatch):
    config = make_config(ssh_enabled=True, ssh_key_path="/key", ssh_host_override="1.2.3.4")
    client = AsyncMock()
    client.get_kasm_status.return_value = {"kasm": {"container_ip": "10.0.0.5"}}
    server = build_server(client, config)

    ssh_exec_mock = AsyncMock(return_value={"stdout": "hi", "stderr": "", "exit_code": 0})
    monkeypatch.setattr("kasm_mcp.ssh.exec_backend.ssh_exec", ssh_exec_mock)

    tool = server._tool_manager.get_tool("execute_kasm_command_ssh")
    result = await tool.run({"kasm_id": "abc", "command": "whoami"}, None)

    assert result["success"] is True
    assert result["stdout"] == "hi"
    ssh_exec_mock.assert_awaited_once_with(
        host="1.2.3.4", port=22, username="kasm-user", key_path="/key",
        command="whoami", working_dir=None,
    )


@pytest.mark.asyncio
async def test_create_kasm_user_tool_forwards_args_to_client():
    config = make_config(admin_mode=True)
    client = AsyncMock()
    client.create_user.return_value = {"user": {"user_id": "u1", "username": "bob"}}
    server = build_server(client, config)

    tool = server._tool_manager.get_tool("create_kasm_user")
    result = await tool.run(
        {"username": "bob", "password": "hunter2", "first_name": "Bob", "group_id": "g1"}, None
    )

    assert result == {"success": True, "user": {"user_id": "u1", "username": "bob"}}
    client.create_user.assert_awaited_once_with(
        username="bob", password="hunter2", first_name="Bob", last_name="", group_id="g1"
    )


@pytest.mark.asyncio
async def test_update_kasm_user_tool_forwards_fields_dict_as_kwargs_to_client():
    """Regression test for finding #1: the `fields` dict param must be
    expanded into individual kwargs when it reaches the client, not
    forwarded as a single nested `fields={...}` kwarg.
    """
    config = make_config(admin_mode=True)
    client = AsyncMock()
    client.update_user.return_value = {"user": {"user_id": "u1", "first_name": "Bob"}}
    server = build_server(client, config)

    tool = server._tool_manager.get_tool("update_kasm_user")
    result = await tool.run({"user_id": "u1", "fields": {"first_name": "Bob"}}, None)

    assert result == {"success": True, "user": {"user_id": "u1", "first_name": "Bob"}}
    client.update_user.assert_awaited_once_with(user_id="u1", first_name="Bob")
