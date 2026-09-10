"""Proves the kasm-mcp console script loads KASM_* vars from a .env file.

Subprocess-based rather than unit-mocked: the thing worth proving is that
``main()`` really reads a .env file sitting next to where it's invoked from,
which only a real process boundary can demonstrate honestly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_console_script_loads_config_from_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "KASM_API_URL=https://kasm.example.com\n"
        "KASM_API_KEY=key123\n"
        "KASM_API_SECRET=secret123\n"
        "KASM_USER_ID=39b31830-1e50-4d1c-90fe-816f89ff6612\n"
    )

    # A bare env (no inherited KASM_* vars) proves the values came from
    # the .env file, not from the test runner's own environment.
    clean_env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "VIRTUAL_ENV": sys.prefix}

    try:
        result = subprocess.run(
            ["kasm-mcp"],
            cwd=tmp_path,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        # Happy path A: config loaded fine, the MCP stdio transport read EOF
        # on stdin (pytest's own stdin isn't interactive) and shut down
        # cleanly — rc=0, nothing on stderr. A config/startup failure would
        # instead exit non-zero with a traceback.
        assert result.returncode == 0, f"unexpected exit {result.returncode}: {result.stderr}"
        assert not result.stderr, f"unexpected stderr: {result.stderr}"
    except subprocess.TimeoutExpired as exc:
        # Happy path B: it's still waiting on stdio when the timeout hit —
        # also proves startup succeeded (a config failure exits almost
        # immediately with a traceback instead of hanging).
        stderr = (exc.stderr or b"").decode()
        assert "Traceback" not in stderr, f"unexpected traceback: {stderr}"


def test_console_script_fails_fast_without_dotenv_or_env_vars(tmp_path: Path) -> None:
    clean_env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "VIRTUAL_ENV": sys.prefix}

    result = subprocess.run(
        ["kasm-mcp"],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode != 0
    assert "Missing required environment variable" in result.stderr
