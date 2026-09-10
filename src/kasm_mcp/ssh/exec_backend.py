"""Optional SSH-backed exec: the only way this project can return real
stdout/stderr/exit_code, since the Kasm Developer API's exec_command_kasm
never does. Only reachable when the caller's network can reach the target
host (same Docker network for a container_ip, or a routable override)."""

from __future__ import annotations

import shlex

import asyncssh


class SSHNotConfiguredError(Exception):
    """Raised when no usable SSH host could be resolved."""


def resolve_ssh_host(*, explicit_host: str | None, override: str | None, container_ip: str | None) -> str:
    """Priority: explicit tool param > KASM_SSH_HOST_OVERRIDE > session's container_ip.

    container_ip only works when the MCP server runs on the same Docker
    network as the Kasm session container — documented, not assumed.
    """
    for candidate in (explicit_host, override, container_ip):
        if candidate:
            return candidate
    raise SSHNotConfiguredError(
        "No SSH host available: pass ssh_host explicitly, set KASM_SSH_HOST_OVERRIDE, "
        "or ensure the session status includes a reachable container_ip."
    )


async def ssh_exec(
    *,
    host: str,
    port: int,
    username: str,
    key_path: str,
    command: str,
    working_dir: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Run a command over SSH and return real stdout/stderr/exit_code."""
    full_command = f"cd {shlex.quote(working_dir)} && {command}" if working_dir else command
    async with asyncssh.connect(
        host, port=port, username=username, client_keys=[key_path], known_hosts=None
    ) as conn:
        result = await conn.run(full_command, check=False, timeout=timeout)
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_status}
