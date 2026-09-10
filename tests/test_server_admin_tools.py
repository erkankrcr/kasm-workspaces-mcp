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


def test_admin_tools_absent_by_default():
    server = build_server(AsyncMock(), make_config())
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "create_kasm_user" not in names
    assert "add_user_to_group" not in names


def test_admin_tools_present_when_admin_mode_enabled():
    server = build_server(AsyncMock(), make_config(admin_mode=True))
    names = {t.name for t in server._tool_manager.list_tools()}
    for expected in (
        "create_kasm_user", "update_kasm_user", "delete_kasm_user",
        "get_kasm_user", "get_kasm_users", "logout_kasm_user",
        "add_user_to_group", "remove_user_from_group",
    ):
        assert expected in names
