from unittest.mock import AsyncMock

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


def test_connect_workspace_tool_absent_by_default():
    server = build_server(AsyncMock(), make_config())
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "connect_workspace" not in names


def test_connect_workspace_tool_present_when_enabled(tmp_path):
    config = make_config(workspace_registry_enabled=True, db_path=str(tmp_path / "registry.db"))
    server = build_server(AsyncMock(), config)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "connect_workspace" in names
