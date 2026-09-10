from unittest.mock import AsyncMock, patch

import pytest

from kasm_mcp.config import KasmConfig
from kasm_mcp.server import build_server


def make_config(**overrides) -> KasmConfig:
    base = dict(
        api_url="https://kasm.example.com",
        api_key="key",
        api_secret="secret",
        user_id="user1",
        allowed_roots=["/home/kasm-user"],
        admin_mode=False,
        unofficial_api=False,
        ssh_enabled=False,
        ssh_key_path=None,
        ssh_user="kasm-user",
        ssh_host_override=None,
    )
    base.update(overrides)
    return KasmConfig(**base)


def test_build_server_omits_ssh_tool_when_disabled():
    server = build_server(AsyncMock(), make_config(ssh_enabled=False))
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    assert "execute_kasm_command_ssh" not in tool_names


@pytest.mark.asyncio
async def test_build_server_registers_ssh_tool_when_enabled():
    config = make_config(ssh_enabled=True, ssh_key_path="/key", ssh_host_override="1.2.3.4")
    server = build_server(AsyncMock(), config)
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    assert "execute_kasm_command_ssh" in tool_names
