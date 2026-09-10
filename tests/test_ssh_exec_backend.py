import shlex
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kasm_mcp.ssh.exec_backend import SSHNotConfiguredError, resolve_ssh_host, ssh_exec


def test_resolve_ssh_host_prefers_explicit_param():
    assert resolve_ssh_host(explicit_host="1.2.3.4", override="5.6.7.8", container_ip="9.9.9.9") == "1.2.3.4"


def test_resolve_ssh_host_falls_back_to_override():
    assert resolve_ssh_host(explicit_host=None, override="5.6.7.8", container_ip="9.9.9.9") == "5.6.7.8"


def test_resolve_ssh_host_falls_back_to_container_ip():
    assert resolve_ssh_host(explicit_host=None, override=None, container_ip="9.9.9.9") == "9.9.9.9"


def test_resolve_ssh_host_raises_when_nothing_available():
    with pytest.raises(SSHNotConfiguredError):
        resolve_ssh_host(explicit_host=None, override=None, container_ip=None)


@pytest.mark.asyncio
async def test_ssh_exec_returns_stdout_stderr_exit_code():
    process = MagicMock()
    process.stdout = "hello\n"
    process.stderr = ""
    process.exit_status = 0

    conn = AsyncMock()
    conn.run.return_value = process
    conn.__aenter__.return_value = conn
    conn.__aexit__.return_value = None

    with patch("kasm_mcp.ssh.exec_backend.asyncssh.connect", return_value=conn) as mock_connect:
        result = await ssh_exec(
            host="1.2.3.4", port=22, username="kasm-user", key_path="/key", command="echo hello"
        )

    assert result == {"stdout": "hello\n", "stderr": "", "exit_code": 0}
    # asyncssh.connect() is a plain (non-async) function that returns an
    # async-context-manager-capable object -- it is *called*, not awaited,
    # so the mock here is a MagicMock and we assert on call, not await.
    mock_connect.assert_called_once()
    _, kwargs = mock_connect.call_args
    assert kwargs["username"] == "kasm-user"
    assert kwargs["client_keys"] == ["/key"]
    assert kwargs["known_hosts"] is None


@pytest.mark.asyncio
async def test_ssh_exec_shell_quotes_working_dir_with_single_quote():
    """A working_dir containing a single quote must not break shell parsing.

    repr() would emit e.g. "cd '/tmp/it\\'s a dir' && ls" -- inside bash
    single-quotes, "\\'" is not an escape, so the quoted region terminates
    at the literal "'" and the rest is parsed as unrelated shell tokens.
    shlex.quote() avoids this by using the '"'"' trick, which is safe.
    """
    process = MagicMock()
    process.stdout = ""
    process.stderr = ""
    process.exit_status = 0

    conn = AsyncMock()
    conn.run.return_value = process
    conn.__aenter__.return_value = conn
    conn.__aexit__.return_value = None

    tricky_dir = "/tmp/it's a dir"

    with patch("kasm_mcp.ssh.exec_backend.asyncssh.connect", return_value=conn):
        await ssh_exec(
            host="1.2.3.4", port=22, username="kasm-user", key_path="/key",
            command="ls", working_dir=tricky_dir,
        )

    sent_command = conn.run.call_args.args[0]
    assert sent_command == f"cd {shlex.quote(tricky_dir)} && ls"
    # Prove it's actually shell-safe: a POSIX-compatible parser must round-trip
    # it back to exactly the intended directory, not a truncated/garbled one.
    parsed = shlex.split(sent_command)
    assert parsed == ["cd", tricky_dir, "&&", "ls"]
