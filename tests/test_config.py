import os

import pytest

from kasm_mcp.config import ConfigError, load_config

REQUIRED = {
    "KASM_API_URL": "https://kasm.example.com",
    "KASM_API_KEY": "key123",
    "KASM_API_SECRET": "secret123",
    "KASM_USER_ID": "39b31830-1e50-4d1c-90fe-816f89ff6612",
}


def test_load_config_minimal():
    cfg = load_config(dict(REQUIRED))
    assert cfg.api_url == "https://kasm.example.com"
    assert cfg.api_key == "key123"
    assert cfg.api_secret == "secret123"
    assert cfg.user_id == REQUIRED["KASM_USER_ID"]
    assert cfg.allowed_roots == ["/home/kasm-user"]
    assert cfg.admin_mode is False
    assert cfg.unofficial_api is False
    assert cfg.ssh_enabled is False
    assert cfg.ssh_user == "kasm-user"
    assert cfg.ssh_key_path is None
    assert cfg.ssh_host_override is None
    assert cfg.workspace_registry_enabled is False
    assert cfg.db_path == os.path.expanduser("~/.local/state/kasm-workspaces-mcp/registry.db")


def test_load_config_workspace_registry_flag_and_custom_db_path():
    env = dict(REQUIRED)
    env["KASM_ENABLE_WORKSPACE_REGISTRY"] = "true"
    env["KASM_DB_PATH"] = "/tmp/custom-registry.db"
    cfg = load_config(env)
    assert cfg.workspace_registry_enabled is True
    assert cfg.db_path == "/tmp/custom-registry.db"


def test_load_config_missing_required_raises():
    env = dict(REQUIRED)
    del env["KASM_API_KEY"]
    with pytest.raises(ConfigError, match="KASM_API_KEY"):
        load_config(env)


def test_load_config_parses_flags_and_roots():
    env = dict(REQUIRED)
    env["KASM_ALLOWED_ROOTS"] = "/home/kasm-user,/tmp"
    env["KASM_ADMIN_MODE"] = "true"
    env["KASM_UNOFFICIAL_API"] = "TRUE"
    env["KASM_SSH_ENABLED"] = "true"
    env["KASM_SSH_KEY_PATH"] = "/home/user/.ssh/id_ed25519"
    env["KASM_SSH_USER"] = "root"
    env["KASM_SSH_HOST_OVERRIDE"] = "10.0.0.5"
    cfg = load_config(env)
    assert cfg.allowed_roots == ["/home/kasm-user", "/tmp"]
    assert cfg.admin_mode is True
    assert cfg.unofficial_api is True
    assert cfg.ssh_enabled is True
    assert cfg.ssh_key_path == "/home/user/.ssh/id_ed25519"
    assert cfg.ssh_user == "root"
    assert cfg.ssh_host_override == "10.0.0.5"


def test_load_config_ssh_enabled_without_key_raises():
    env = dict(REQUIRED)
    env["KASM_SSH_ENABLED"] = "true"
    with pytest.raises(ConfigError, match="KASM_SSH_KEY_PATH"):
        load_config(env)
