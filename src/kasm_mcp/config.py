"""Environment-driven configuration for kasm-workspaces-mcp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

_REQUIRED = ("KASM_API_URL", "KASM_API_KEY", "KASM_API_SECRET", "KASM_USER_ID")
_TRUE = {"true", "1", "yes", "on"}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class KasmConfig:
    api_url: str
    api_key: str
    api_secret: str
    user_id: str
    allowed_roots: list[str]
    admin_mode: bool
    unofficial_api: bool
    ssh_enabled: bool
    ssh_key_path: str | None
    ssh_user: str
    ssh_host_override: str | None


def _flag(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in _TRUE


def load_config(env: Mapping[str, str] | None = None) -> KasmConfig:
    """Load and validate configuration from an environment mapping.

    Args:
        env: mapping to read from; defaults to ``os.environ``.

    Raises:
        ConfigError: a required variable is missing, or a dependent
            variable (e.g. an SSH key path when SSH is enabled) is missing.
    """
    if env is None:
        import os

        env = os.environ

    missing = [name for name in _REQUIRED if not env.get(name)]
    if missing:
        raise ConfigError(f"Missing required environment variable(s): {', '.join(missing)}")

    ssh_enabled = _flag(env, "KASM_SSH_ENABLED")
    ssh_key_path = env.get("KASM_SSH_KEY_PATH") or None
    if ssh_enabled and not ssh_key_path:
        raise ConfigError("KASM_SSH_ENABLED is true but KASM_SSH_KEY_PATH is not set")

    roots_raw = env.get("KASM_ALLOWED_ROOTS", "/home/kasm-user")
    allowed_roots = [r.strip() for r in roots_raw.split(",") if r.strip()]

    return KasmConfig(
        api_url=env["KASM_API_URL"],
        api_key=env["KASM_API_KEY"],
        api_secret=env["KASM_API_SECRET"],
        user_id=env["KASM_USER_ID"],
        allowed_roots=allowed_roots,
        admin_mode=_flag(env, "KASM_ADMIN_MODE"),
        unofficial_api=_flag(env, "KASM_UNOFFICIAL_API"),
        ssh_enabled=ssh_enabled,
        ssh_key_path=ssh_key_path,
        ssh_user=env.get("KASM_SSH_USER", "kasm-user"),
        ssh_host_override=env.get("KASM_SSH_HOST_OVERRIDE") or None,
    )
