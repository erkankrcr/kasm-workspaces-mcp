from unittest.mock import AsyncMock

from kasm_mcp.config import KasmConfig
from kasm_mcp.server import build_server


def make_config(**overrides) -> KasmConfig:
    base = dict(
        api_url="https://kasm.example.com", api_key="key", api_secret="secret", user_id="user1",
        allowed_roots=["/home/kasm-user"], admin_mode=False, unofficial_api=False,
        ssh_enabled=False, ssh_key_path=None, ssh_user="kasm-user", ssh_host_override=None,
    )
    base.update(overrides)
    return KasmConfig(**base)


def test_unofficial_tools_absent_by_default():
    server = build_server(AsyncMock(), make_config())
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "get_registries" not in names


def test_unofficial_tools_present_when_enabled():
    server = build_server(AsyncMock(), make_config(unofficial_api=True))
    names = {t.name for t in server._tool_manager.list_tools()}
    for expected in ("get_registries", "create_registry", "delete_registry", "create_workspace_image", "update_workspace_image", "delete_workspace_image"):
        assert expected in names
