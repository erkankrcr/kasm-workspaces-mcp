# kasm-workspaces-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an original (non-copied), MIT-licensed MCP server for Kasm Workspaces that only claims behavior verified against the real Kasm Developer API, with layered opt-in tool surfaces (scoped / SSH-exec / admin / unofficial-admin-panel).

**Architecture:** `src/kasm_mcp/` splits into `config.py` (env loading), `security/validation.py` (input validation), `api/http.py` (shared HTTP primitives), `api/client.py` (Kasm Developer API), `ssh/exec_backend.py` (optional real-output exec), `admin_unofficial/client.py` (opt-in `/api/admin/*` wrapper), and `server.py` (MCP tool registration via a `build_server(client, config)` factory, with tool logic in plain testable functions that FastMCP-decorated closures delegate to).

**Tech Stack:** Python 3.10+, `mcp` (official SDK, FastMCP), `aiohttp`, `asyncssh` (optional), `pytest` + `pytest-asyncio` + `aioresponses`, `ruff`, `mypy`, `hatchling`.

**Spec:** `docs/superpowers/specs/2026-09-10-kasm-workspaces-mcp-design.md`

## Global Constraints

- Never put secrets (API key/secret, SSH private key contents) in subprocess command-line arguments or logs.
- `KASM_ADMIN_MODE`, `KASM_UNOFFICIAL_API`, `KASM_SSH_ENABLED` all default to `false`; each gates its tool set independently.
- No fabricated success: `execute_kasm_command` never claims an `exit_code`/`output` the real Kasm API doesn't return.
- `api/client.py` methods only implement behavior verified this session (or, for admin/unofficial, verified live during Task 9/10) — no guessed response shapes.
- All async HTTP goes through `api/http.py`'s shared primitives — no duplicate request-building logic.
- License: MIT. Repo: `kasm-workspaces-mcp` (local path `/home/ekaracar/kasm-workspaces-mcp`, already `git init`'d with the spec committed as `12946f2`).

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/kasm_mcp/__init__.py`
- Create: `src/kasm_mcp/py.typed`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Produces: an installable `kasm_mcp` package (importable, `__version__` string) that every later task builds on.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package.py
import kasm_mcp


def test_package_has_version():
    assert isinstance(kasm_mcp.__version__, str)
    assert kasm_mcp.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && python3 -m venv .venv && .venv/bin/pip install -q -e . 2>&1 | tail -5 || true; .venv/bin/pip install -q pytest 2>&1 | tail -5; .venv/bin/pytest tests/test_package.py -v`
Expected: FAIL (package/module not found, since `src/kasm_mcp/__init__.py` doesn't exist yet and isn't installed)

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/__init__.py
"""kasm-workspaces-mcp: an MCP server for managing Kasm Workspaces sessions."""

__version__ = "0.1.0"
```

```
# src/kasm_mcp/py.typed
```
(empty marker file for PEP 561)

```toml
# pyproject.toml
[project]
name = "kasm-workspaces-mcp"
version = "0.1.0"
description = "MCP server for managing Kasm Workspaces sessions"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = [
    "mcp>=1.0.0",
    "aiohttp>=3.9.0",
]

[project.optional-dependencies]
ssh = ["asyncssh>=2.14.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "aioresponses>=0.7.6",
    "ruff>=0.4.0",
    "mypy>=1.9.0",
]

[project.scripts]
kasm-mcp = "kasm_mcp.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/kasm_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.mypy]
python_version = "3.10"
packages = ["kasm_mcp"]
```

```
# .gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
.env
```

```
# LICENSE
MIT License

Copyright (c) 2026 erkankrcr

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pip install -q -e ".[dev]" && .venv/bin/pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add pyproject.toml src/kasm_mcp/__init__.py src/kasm_mcp/py.typed .gitignore LICENSE tests/__init__.py tests/test_package.py
git commit -m "chore: project scaffolding (pyproject, package skeleton, MIT license)"
```

---

## Task 2: Config loading

**Files:**
- Create: `src/kasm_mcp/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (reads from `os.environ` / an injectable mapping)
- Produces: `KasmConfig` (frozen dataclass) and `ConfigError`, `load_config(env: Mapping[str, str] | None = None) -> KasmConfig` — used by every later task that needs settings.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/config.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/config.py tests/test_config.py
git commit -m "feat: env-driven config loading with fail-fast validation"
```

---

## Task 3: Security validation

**Files:**
- Create: `src/kasm_mcp/security/__init__.py`
- Create: `src/kasm_mcp/security/validation.py`
- Test: `tests/test_security_validation.py`

**Interfaces:**
- Consumes: nothing
- Produces: `SecurityError`, `validate_command(command: str) -> None`, `validate_path(path: str, allowed_roots: list[str], operation: str = "access") -> None` — used by `server.py` (Task 7) before dispatching exec/file operations.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_security_validation.py
import pytest

from kasm_mcp.security.validation import SecurityError, validate_command, validate_path


@pytest.mark.parametrize(
    "command",
    [
        "cat /etc/passwd | grep root",
        "ls; rm -rf /",
        "echo a && echo b",
        "echo a || echo b",
        "echo `whoami`",
        "echo $(whoami)",
        "cat file >> out.txt",
        "cat file > out.txt",
        "cat < file",
        "cd ../../etc",
    ],
)
def test_validate_command_rejects_dangerous_patterns(command):
    with pytest.raises(SecurityError):
        validate_command(command)


@pytest.mark.parametrize(
    "command",
    ["nmap -sV 10.0.0.1", "whoami", "chromium https://example.com", "ls -la /home/kasm-user"],
)
def test_validate_command_allows_plain_commands(command):
    validate_command(command)  # must not raise


def test_validate_path_allows_within_root():
    validate_path("/home/kasm-user/results.txt", ["/home/kasm-user", "/tmp"])


def test_validate_path_rejects_outside_roots():
    with pytest.raises(SecurityError):
        validate_path("/etc/passwd", ["/home/kasm-user", "/tmp"])


def test_validate_path_rejects_traversal_even_if_prefix_matches():
    with pytest.raises(SecurityError):
        validate_path("/home/kasm-user/../../etc/passwd", ["/home/kasm-user"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_security_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.security'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/security/__init__.py
```

```python
# src/kasm_mcp/security/validation.py
"""Input validation shared by every tool that touches the Kasm session shell."""

from __future__ import annotations

import os

_DANGEROUS_COMMAND_PATTERNS = ("|", ";", "&&", "||", "`", "$(", "${", ">>", ">", "<")


class SecurityError(Exception):
    """Raised when a command or path fails a security check."""


def validate_command(command: str) -> None:
    """Reject commands using shell metacharacters that enable chaining/injection.

    This is deliberately conservative: callers needing pipelines must run
    a pre-written script file instead of relying on shell chaining here.
    """
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern in command:
            raise SecurityError(f"command contains disallowed pattern: {pattern!r}")


def validate_path(path: str, allowed_roots: list[str], operation: str = "access") -> None:
    """Reject a path that isn't (after resolving `..`) under one of allowed_roots."""
    normalized = os.path.normpath(path)
    if not os.path.isabs(normalized):
        raise SecurityError(f"path must be absolute for {operation}: {path!r}")
    for root in allowed_roots:
        root_norm = os.path.normpath(root)
        if normalized == root_norm or normalized.startswith(root_norm + os.sep):
            return
    raise SecurityError(f"path {path!r} is outside allowed roots {allowed_roots} for {operation}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_security_validation.py -v`
Expected: PASS (all parametrized cases)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/security/ tests/test_security_validation.py
git commit -m "feat: command and path validation against injection"
```

---

## Task 4: Shared HTTP primitives

**Files:**
- Create: `src/kasm_mcp/api/__init__.py`
- Create: `src/kasm_mcp/api/http.py`
- Test: `tests/test_api_http.py`

**Interfaces:**
- Consumes: `aiohttp.ClientSession`
- Produces: `KasmAPIError`, `async def request_json(session, api_url, api_key, api_secret, method, path, data=None) -> dict`, `async def request_binary(session, api_url, api_key, api_secret, method, path, data=None) -> bytes` — used by `api/client.py` (Task 5/6/9) and `admin_unofficial/client.py` (Task 10).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_http.py
import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.http import KasmAPIError, request_binary, request_json

API_URL = "https://kasm.example.com"


@pytest.mark.asyncio
async def test_request_json_success_injects_auth_and_returns_body():
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_kasm_status", payload={"kasm": {"operational_status": "running"}})
        async with aiohttp.ClientSession() as session:
            result = await request_json(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_status", {"kasm_id": "abc"}
            )
        assert result == {"kasm": {"operational_status": "running"}}
        request = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/get_kasm_status"))][0]
        sent = request.kwargs["json"]
        assert sent["api_key"] == "key"
        assert sent["api_key_secret"] == "secret"
        assert sent["kasm_id"] == "abc"


@pytest.mark.asyncio
async def test_request_json_raises_on_error_status():
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", status=400, payload={"error_message": "no resources"})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_json_raises_on_error_message_even_with_200():
    # Kasm sometimes returns HTTP 200 with an error_message body (observed live
    # for "No resources are available to create the requested Kasm").
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", status=200, payload={"error_message": "no resources"})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="no resources"):
                await request_json(session, API_URL, "key", "secret", "POST", "/api/public/request_kasm", {})


@pytest.mark.asyncio
async def test_request_binary_returns_raw_bytes():
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            body=b"\xff\xd8\xff\xe0fakejpeg",
            content_type="image/jpeg",
        )
        async with aiohttp.ClientSession() as session:
            result = await request_binary(
                session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {"kasm_id": "abc"}
            )
        assert result == b"\xff\xd8\xff\xe0fakejpeg"


@pytest.mark.asyncio
async def test_request_binary_raises_on_json_error_body():
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            status=400,
            payload={"error_message": "bad kasm_id"},
        )
        async with aiohttp.ClientSession() as session:
            with pytest.raises(KasmAPIError, match="bad kasm_id"):
                await request_binary(
                    session, API_URL, "key", "secret", "POST", "/api/public/get_kasm_screenshot", {}
                )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pip install -q aioresponses && .venv/bin/pytest tests/test_api_http.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.api'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/api/__init__.py
```

```python
# src/kasm_mcp/api/http.py
"""Low-level authenticated HTTP calls to the Kasm Developer API.

Shared by api/client.py (``/api/public/*``) and admin_unofficial/client.py
(``/api/admin/*`` — same api_key auth, per Kasm's own "Using Undocumented
APIs" support guidance).
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urljoin

import aiohttp


class KasmAPIError(Exception):
    """Raised for any non-successful Kasm API response."""


def _error_message(status: int, body: Mapping[str, Any]) -> str:
    return str(body.get("error_message") or body.get("error") or f"HTTP {status}")


async def request_json(
    session: aiohttp.ClientSession,
    api_url: str,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    data: Mapping[str, Any] | None = None,
) -> dict:
    """POST/GET a Kasm endpoint expecting a JSON body back.

    Raises KasmAPIError both for HTTP >=400 responses and for HTTP 200
    responses that carry an ``error_message``/``error`` field — Kasm does
    both depending on the failure (observed live: "No resources are
    available..." comes back as a 200 with error_message).
    """
    body = {"api_key": api_key, "api_key_secret": api_secret, **(data or {})}
    url = urljoin(api_url.rstrip("/") + "/", path.lstrip("/"))
    async with session.request(method, url, json=body) as resp:
        payload = await resp.json()
        if resp.status >= 400 or "error_message" in payload or "error" in payload:
            raise KasmAPIError(_error_message(resp.status, payload))
        return payload


async def request_binary(
    session: aiohttp.ClientSession,
    api_url: str,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    data: Mapping[str, Any] | None = None,
) -> bytes:
    """POST a Kasm endpoint expecting a raw binary body back (e.g. a JPEG screenshot)."""
    body = {"api_key": api_key, "api_key_secret": api_secret, **(data or {})}
    url = urljoin(api_url.rstrip("/") + "/", path.lstrip("/"))
    async with session.request(method, url, json=body) as resp:
        content_type = resp.headers.get("content-type", "")
        if resp.status >= 400 or "application/json" in content_type:
            payload = await resp.json()
            raise KasmAPIError(_error_message(resp.status, payload))
        return await resp.read()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_http.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/api/__init__.py src/kasm_mcp/api/http.py tests/test_api_http.py
git commit -m "feat: shared authenticated HTTP primitives for the Kasm API"
```

---

## Task 5: Session-lifecycle client methods

**Files:**
- Create: `src/kasm_mcp/api/client.py`
- Create: `tests/fixtures/get_kasm_status_response.json`
- Test: `tests/test_api_client_sessions.py`

**Interfaces:**
- Consumes: `request_json` from `api/http.py` (Task 4)
- Produces: `KasmAPIClient` with `__init__(api_url, api_key, api_secret)`, `close()`, `request_kasm(*, image_name, user_id, group_id, enable_sharing=False)`, `get_kasm_status(*, kasm_id, user_id)`, `destroy_kasm(*, kasm_id, user_id)`, `get_user_kasms(*, user_id)`, `get_kasms()`, `pause_kasm(*, kasm_id, user_id)`, `resume_kasm(*, kasm_id, user_id)` — used by `server.py` (Task 7).

- [ ] **Step 1: Write the failing test**

```json
// tests/fixtures/get_kasm_status_response.json
{
  "kasm": {
    "kasm_id": "b057c3754cb6499cb8d3afeadd6bf0fc",
    "operational_status": "running",
    "container_ip": "172.18.0.4",
    "host": "10.0.0.120",
    "port": 443,
    "share_id": null,
    "view_only_token": "",
    "username": "claude",
    "user_id": "39b318301e504d1c90fe816f89ff6612",
    "image": {
      "image_id": "c7af5cfaf7a649b69afd948f11199bd1",
      "name": "kasmweb/chromium:1.19.0",
      "friendly_name": "Chromium"
    },
    "port_map": {
      "vnc": {"path": "desktop/b057c375-4cb6-499c-b8d3-afeadd6bf0fc/vnc", "port": 443}
    }
  },
  "current_time": "2026-09-10T12:52:49Z"
}
```
(This is the real shape captured live this session, with identifiers left as originally observed — nothing secret in it.)

```python
# tests/test_api_client_sessions.py
import json
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.api.http import KasmAPIError

API_URL = "https://kasm.example.com"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
async def client():
    c = KasmAPIClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_request_kasm_without_sharing_omits_enable_sharing_field(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", payload={"kasm_id": "abc", "kasm_url": "/#/connect/kasm/abc", "share_id": None, "status": "starting"})
        result = await client.request_kasm(image_name="img123", user_id="user1", group_id="group1")
    assert result["kasm_id"] == "abc"
    assert result["share_id"] is None
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/request_kasm"))][0].kwargs["json"]
    assert "enable_sharing" not in sent
    assert sent["image_name"] == "img123"
    assert sent["group_id"] == "group1"


@pytest.mark.asyncio
async def test_request_kasm_with_sharing_sets_enable_sharing_true(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/request_kasm", payload={"kasm_id": "abc", "share_id": "c20d04e8", "status": "starting"})
        result = await client.request_kasm(image_name="img123", user_id="user1", group_id="group1", enable_sharing=True)
    assert result["share_id"] == "c20d04e8"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/request_kasm"))][0].kwargs["json"]
    assert sent["enable_sharing"] is True


@pytest.mark.asyncio
async def test_get_kasm_status_returns_full_fixture_shape(client):
    fixture = json.loads((FIXTURES / "get_kasm_status_response.json").read_text())
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_kasm_status", payload=fixture)
        result = await client.get_kasm_status(kasm_id="b057c375...", user_id="user1")
    assert result["kasm"]["operational_status"] == "running"
    assert result["kasm"]["share_id"] is None


@pytest.mark.asyncio
async def test_destroy_kasm_raises_kasm_api_error_on_failure(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/destroy_kasm", status=400, payload={"error_message": "not found"})
        with pytest.raises(KasmAPIError, match="not found"):
            await client.destroy_kasm(kasm_id="missing", user_id="user1")


@pytest.mark.asyncio
async def test_get_user_kasms_and_get_kasms_and_pause_resume(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_user_kasms", payload={"kasms": []})
        m.post(f"{API_URL}/api/public/get_kasms", payload={"kasms": []})
        m.post(f"{API_URL}/api/public/pause_kasm", payload={"status": "paused"})
        m.post(f"{API_URL}/api/public/resume_kasm", payload={"status": "running"})
        assert await client.get_user_kasms(user_id="user1") == {"kasms": []}
        assert await client.get_kasms() == {"kasms": []}
        assert await client.pause_kasm(kasm_id="abc", user_id="user1") == {"status": "paused"}
        assert await client.resume_kasm(kasm_id="abc", user_id="user1") == {"status": "running"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && mkdir -p tests/fixtures && .venv/bin/pytest tests/test_api_client_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.api.client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/api/client.py
"""Async client for the Kasm Developer API (``/api/public/*``).

Every method here implements behavior verified live against a real Kasm
instance this project's design session — see docs/API_BEHAVIOR.md.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from kasm_mcp.api.http import request_binary, request_json


class KasmAPIClient:
    def __init__(self, api_url: str, api_key: str, api_secret: str) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _json(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict:
        return await request_json(
            self._get_session(), self._api_url, self._api_key, self._api_secret, method, path, data
        )

    async def _binary(self, method: str, path: str, data: dict[str, Any] | None = None) -> bytes:
        return await request_binary(
            self._get_session(), self._api_url, self._api_key, self._api_secret, method, path, data
        )

    async def request_kasm(
        self, *, image_name: str, user_id: str, group_id: str, enable_sharing: bool = False
    ) -> dict:
        data: dict[str, Any] = {"image_name": image_name, "user_id": user_id, "group_id": group_id}
        if enable_sharing:
            data["enable_sharing"] = True
        return await self._json("POST", "/api/public/request_kasm", data)

    async def get_kasm_status(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/get_kasm_status", {"kasm_id": kasm_id, "user_id": user_id})

    async def destroy_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/destroy_kasm", {"kasm_id": kasm_id, "user_id": user_id})

    async def get_user_kasms(self, *, user_id: str) -> dict:
        return await self._json("POST", "/api/public/get_user_kasms", {"user_id": user_id})

    async def get_kasms(self) -> dict:
        return await self._json("POST", "/api/public/get_kasms")

    async def pause_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/pause_kasm", {"kasm_id": kasm_id, "user_id": user_id})

    async def resume_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/resume_kasm", {"kasm_id": kasm_id, "user_id": user_id})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_client_sessions.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/api/client.py tests/fixtures/get_kasm_status_response.json tests/test_api_client_sessions.py
git commit -m "feat: session-lifecycle Kasm API client methods"
```

---

## Task 6: Screenshot, exec, sharing, images client methods

**Files:**
- Modify: `src/kasm_mcp/api/client.py`
- Test: `tests/test_api_client_exec_screenshot.py`

**Interfaces:**
- Consumes: `KasmAPIClient` from Task 5
- Produces: additions to `KasmAPIClient`: `get_kasm_screenshot(*, kasm_id, user_id, width=None, height=None) -> bytes`, `exec_command(*, kasm_id, user_id, command, working_dir=None, user=None) -> None`, `join_kasm(*, share_id, user_id=None) -> dict`, `get_images() -> dict` — used by `server.py` (Task 7).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_client_exec_screenshot.py
import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.client import KasmAPIClient

API_URL = "https://kasm.example.com"


@pytest.fixture
async def client():
    c = KasmAPIClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_get_kasm_screenshot_returns_raw_bytes_not_json(client):
    with aioresponses() as m:
        m.post(
            f"{API_URL}/api/public/get_kasm_screenshot",
            body=b"\xff\xd8\xff\xe0fakejpeg",
            content_type="image/jpeg",
        )
        result = await client.get_kasm_screenshot(kasm_id="abc", user_id="user1", width=1600, height=900)
    assert result == b"\xff\xd8\xff\xe0fakejpeg"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/get_kasm_screenshot"))][0].kwargs["json"]
    assert sent["width"] == 1600
    assert sent["height"] == 900


@pytest.mark.asyncio
async def test_exec_command_returns_none_it_never_carries_output(client):
    # exec_command_kasm is fire-and-forget on the real API: no stdout/exit_code
    # field exists to return, so this method's contract is "dispatched or raised",
    # never a fabricated result.
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/exec_command_kasm", payload={"kasm": {}, "current_time": "now"})
        result = await client.exec_command(kasm_id="abc", user_id="user1", command="whoami", user="kasm-user")
    assert result is None
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/exec_command_kasm"))][0].kwargs["json"]
    assert sent["exec_config"]["cmd"] == "whoami"
    assert sent["exec_config"]["user"] == "kasm-user"


@pytest.mark.asyncio
async def test_join_kasm_without_user_id_omits_field(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/join_kasm", payload={"kasm_url": "/#/connect/join/abc/anon/token"})
        result = await client.join_kasm(share_id="abc")
    assert result["kasm_url"] == "/#/connect/join/abc/anon/token"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/join_kasm"))][0].kwargs["json"]
    assert "user_id" not in sent


@pytest.mark.asyncio
async def test_get_images_returns_payload(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_images", payload={"images": [{"image_id": "abc", "friendly_name": "Chromium"}]})
        result = await client.get_images()
    assert result["images"][0]["friendly_name"] == "Chromium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_client_exec_screenshot.py -v`
Expected: FAIL with `AttributeError: 'KasmAPIClient' object has no attribute 'get_kasm_screenshot'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/kasm_mcp/api/client.py` (inside the `KasmAPIClient` class, after `resume_kasm`):

```python
    async def get_kasm_screenshot(
        self, *, kasm_id: str, user_id: str, width: int | None = None, height: int | None = None
    ) -> bytes:
        data: dict[str, Any] = {"kasm_id": kasm_id, "user_id": user_id}
        if width:
            data["width"] = width
        if height:
            data["height"] = height
        return await self._binary("POST", "/api/public/get_kasm_screenshot", data)

    async def exec_command(
        self,
        *,
        kasm_id: str,
        user_id: str,
        command: str,
        working_dir: str | None = None,
        user: str | None = None,
    ) -> None:
        """Fire-and-forget: the real Kasm API never returns stdout/exit_code
        for this call, so this method's return is always ``None`` on success;
        it only raises ``KasmAPIError`` if the *dispatch itself* failed."""
        exec_config: dict[str, Any] = {"cmd": command}
        if working_dir:
            exec_config["workdir"] = working_dir
        if user:
            exec_config["user"] = user
        await self._json(
            "POST",
            "/api/public/exec_command_kasm",
            {"kasm_id": kasm_id, "user_id": user_id, "exec_config": exec_config},
        )
        return None

    async def join_kasm(self, *, share_id: str, user_id: str | None = None) -> dict:
        data: dict[str, Any] = {"share_id": share_id}
        if user_id:
            data["user_id"] = user_id
        return await self._json("POST", "/api/public/join_kasm", data)

    async def get_images(self) -> dict:
        return await self._json("POST", "/api/public/get_images")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_client_exec_screenshot.py tests/test_api_client_sessions.py -v`
Expected: PASS (all tests, both files)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/api/client.py tests/test_api_client_exec_screenshot.py
git commit -m "feat: screenshot, exec, share-join, and image-list client methods"
```

---

## Task 7: Scoped-mode MCP server

**Files:**
- Create: `src/kasm_mcp/server.py`
- Create: `src/kasm_mcp/__main__.py`
- Test: `tests/test_server_scoped_tools.py`

**Interfaces:**
- Consumes: `KasmConfig` (Task 2), `SecurityError`/`validate_command` (Task 3), `KasmAPIClient`/`KasmAPIError` (Tasks 5-6)
- Produces: plain async logic functions (`create_kasm_session_logic`, `destroy_kasm_session_logic`, `pause_kasm_session_logic`, `resume_kasm_session_logic`, `get_session_status_logic`, `list_user_sessions_logic`, `get_share_link_logic`, `get_session_screenshot_logic`, `execute_kasm_command_logic`, `get_available_workspaces_logic`) each `(client, config, **kwargs) -> dict`, plus `build_server(client, config) -> FastMCP` that registers scoped tools and conditionally wires Tasks 8-10. Used directly by tests; `build_server` used by `__main__.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_scoped_tools.py
from unittest.mock import AsyncMock

import pytest

from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.security.validation import SecurityError
from kasm_mcp.server import (
    create_kasm_session_logic,
    destroy_kasm_session_logic,
    execute_kasm_command_logic,
    get_session_screenshot_logic,
    get_session_status_logic,
    get_share_link_logic,
    list_user_sessions_logic,
)


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


@pytest.mark.asyncio
async def test_create_kasm_session_logic_success():
    client = AsyncMock()
    client.request_kasm.return_value = {"kasm_id": "abc", "kasm_url": "/#/connect/kasm/abc", "share_id": None, "status": "starting"}
    result = await create_kasm_session_logic(client, make_config(), image_name="img", group_id="grp")
    assert result == {
        "success": True,
        "kasm_id": "abc",
        "session_url": "/#/connect/kasm/abc",
        "share_id": None,
        "status": "starting",
    }
    client.request_kasm.assert_awaited_once_with(image_name="img", user_id="user1", group_id="grp", enable_sharing=False)


@pytest.mark.asyncio
async def test_create_kasm_session_logic_api_error_returns_success_false():
    client = AsyncMock()
    client.request_kasm.side_effect = KasmAPIError("no resources")
    result = await create_kasm_session_logic(client, make_config(), image_name="img", group_id="grp")
    assert result == {"success": False, "error": "no resources"}


@pytest.mark.asyncio
async def test_destroy_kasm_session_logic_success():
    client = AsyncMock()
    client.destroy_kasm.return_value = {}
    result = await destroy_kasm_session_logic(client, make_config(), kasm_id="abc")
    assert result == {"success": True, "kasm_id": "abc"}
    client.destroy_kasm.assert_awaited_once_with(kasm_id="abc", user_id="user1")


@pytest.mark.asyncio
async def test_get_session_status_logic_success():
    client = AsyncMock()
    client.get_kasm_status.return_value = {"kasm": {"operational_status": "running"}}
    result = await get_session_status_logic(client, make_config(), kasm_id="abc")
    assert result == {"success": True, "kasm_id": "abc", "status": {"operational_status": "running"}}


@pytest.mark.asyncio
async def test_list_user_sessions_logic_success():
    client = AsyncMock()
    client.get_user_kasms.return_value = {"kasms": [{"kasm_id": "abc"}]}
    result = await list_user_sessions_logic(client, make_config())
    assert result == {"success": True, "sessions": [{"kasm_id": "abc"}]}


@pytest.mark.asyncio
async def test_get_share_link_logic_returns_url_with_view_only_note():
    client = AsyncMock()
    client.join_kasm.return_value = {"kasm_url": "/#/connect/join/abc/anon/token"}
    result = await get_share_link_logic(client, make_config(), share_id="abc")
    assert result["success"] is True
    assert result["share_url"] == "/#/connect/join/abc/anon/token"
    assert "view-only" in result["note"].lower()


@pytest.mark.asyncio
async def test_get_session_screenshot_logic_saves_to_file(tmp_path):
    client = AsyncMock()
    client.get_kasm_screenshot.return_value = b"\xff\xd8\xff\xe0fake"
    dest = tmp_path / "shot.jpg"
    result = await get_session_screenshot_logic(client, make_config(), kasm_id="abc", save_to_file=str(dest))
    assert result == {"success": True, "kasm_id": "abc", "file_path": str(dest)}
    assert dest.read_bytes() == b"\xff\xd8\xff\xe0fake"


@pytest.mark.asyncio
async def test_get_session_screenshot_logic_returns_base64_without_save_path():
    import base64

    client = AsyncMock()
    client.get_kasm_screenshot.return_value = b"\xff\xd8\xff\xe0fake"
    result = await get_session_screenshot_logic(client, make_config(), kasm_id="abc")
    assert result["success"] is True
    assert base64.b64decode(result["screenshot_base64"]) == b"\xff\xd8\xff\xe0fake"


@pytest.mark.asyncio
async def test_execute_kasm_command_logic_rejects_dangerous_command_without_calling_api():
    client = AsyncMock()
    result = await execute_kasm_command_logic(client, make_config(), kasm_id="abc", command="ls; rm -rf /")
    assert result["success"] is False
    assert result["error_type"] == "security"
    client.exec_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_kasm_command_logic_dispatches_and_is_honest_about_output():
    client = AsyncMock()
    client.exec_command.return_value = None
    result = await execute_kasm_command_logic(client, make_config(), kasm_id="abc", command="whoami", user="kasm-user")
    assert result["success"] is True
    assert result["dispatched"] is True
    assert "output" not in result
    assert "exit_code" not in result
    client.exec_command.assert_awaited_once_with(
        kasm_id="abc", user_id="user1", command="whoami", working_dir=None, user="kasm-user"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_server_scoped_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/server.py
"""MCP tool registration for kasm-workspaces-mcp.

Tool *logic* lives in plain async functions (client, config, **kwargs) -> dict
so it's testable without going through the MCP protocol. ``build_server``
wires those functions into FastMCP-decorated closures.
"""

from __future__ import annotations

import base64
from typing import Any

from mcp.server.fastmcp import FastMCP

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.security.validation import SecurityError, validate_command

# ---------------------------------------------------------------------------
# Scoped-mode logic functions
# ---------------------------------------------------------------------------


async def create_kasm_session_logic(
    client: KasmAPIClient, config: KasmConfig, *, image_name: str, group_id: str, enable_sharing: bool = False
) -> dict:
    try:
        result = await client.request_kasm(
            image_name=image_name, user_id=config.user_id, group_id=group_id, enable_sharing=enable_sharing
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "kasm_id": result.get("kasm_id"),
        "session_url": result.get("kasm_url"),
        "share_id": result.get("share_id"),
        "status": result.get("status", "created"),
    }


async def destroy_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.destroy_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def pause_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.pause_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def resume_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.resume_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def get_session_status_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        result = await client.get_kasm_status(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id, "status": result.get("kasm", result)}


async def list_user_sessions_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_user_kasms(user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "sessions": result.get("kasms", [])}


async def get_share_link_logic(client: KasmAPIClient, config: KasmConfig, *, share_id: str) -> dict:
    try:
        result = await client.join_kasm(share_id=share_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "share_url": result.get("kasm_url"),
        "note": "View-only link unless the Kasm group's shared_session_full_control setting is enabled.",
    }


async def get_session_screenshot_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    width: int | None = None,
    height: int | None = None,
    save_to_file: str | None = None,
) -> dict:
    try:
        image_bytes = await client.get_kasm_screenshot(kasm_id=kasm_id, user_id=config.user_id, width=width, height=height)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    if save_to_file:
        with open(save_to_file, "wb") as f:
            f.write(image_bytes)
        return {"success": True, "kasm_id": kasm_id, "file_path": save_to_file}
    return {"success": True, "kasm_id": kasm_id, "screenshot_base64": base64.b64encode(image_bytes).decode()}


async def execute_kasm_command_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    command: str,
    working_dir: str | None = None,
    user: str | None = None,
) -> dict:
    try:
        validate_command(command)
    except SecurityError as e:
        return {"success": False, "error": str(e), "error_type": "security"}
    try:
        await client.exec_command(
            kasm_id=kasm_id, user_id=config.user_id, command=command, working_dir=working_dir, user=user
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "dispatched": True,
        "note": "Kasm's exec API never returns command output or exit code; this only confirms dispatch.",
    }


async def get_available_workspaces_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_images()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "images": result.get("images", [])}


# ---------------------------------------------------------------------------
# FastMCP wiring
# ---------------------------------------------------------------------------


def build_server(client: KasmAPIClient, config: KasmConfig) -> FastMCP:
    mcp = FastMCP("kasm-workspaces-mcp")

    @mcp.tool()
    async def create_kasm_session(image_name: str, group_id: str, enable_sharing: bool = False) -> dict:
        """Create a new Kasm session. Set enable_sharing=True to get a usable share_id back."""
        return await create_kasm_session_logic(client, config, image_name=image_name, group_id=group_id, enable_sharing=enable_sharing)

    @mcp.tool()
    async def destroy_kasm_session(kasm_id: str) -> dict:
        """Permanently destroy a Kasm session."""
        return await destroy_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def pause_kasm_session(kasm_id: str) -> dict:
        """Pause a Kasm session."""
        return await pause_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def resume_kasm_session(kasm_id: str) -> dict:
        """Resume a paused Kasm session."""
        return await resume_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def get_session_status(kasm_id: str) -> dict:
        """Get the current status of a Kasm session."""
        return await get_session_status_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def list_user_sessions() -> dict:
        """List active sessions for the configured user."""
        return await list_user_sessions_logic(client, config)

    @mcp.tool()
    async def get_share_link(share_id: str) -> dict:
        """Get a view-only share link for a session created with enable_sharing=True."""
        return await get_share_link_logic(client, config, share_id=share_id)

    @mcp.tool()
    async def get_session_screenshot(
        kasm_id: str, width: int | None = None, height: int | None = None, save_to_file: str | None = None
    ) -> dict:
        """Capture a screenshot of a session. Pass save_to_file to write a JPEG; otherwise returns base64."""
        return await get_session_screenshot_logic(
            client, config, kasm_id=kasm_id, width=width, height=height, save_to_file=save_to_file
        )

    @mcp.tool()
    async def execute_kasm_command(
        kasm_id: str, command: str, working_dir: str | None = None, user: str | None = None
    ) -> dict:
        """Dispatch a command inside a session. Kasm's API never returns output/exit_code for this call."""
        return await execute_kasm_command_logic(
            client, config, kasm_id=kasm_id, command=command, working_dir=working_dir, user=user
        )

    @mcp.tool()
    async def get_available_workspaces() -> dict:
        """List available workspace images."""
        return await get_available_workspaces_logic(client, config)

    return mcp
```

```python
# src/kasm_mcp/__main__.py
"""Entrypoint: ``python -m kasm_mcp`` / the ``kasm-mcp`` console script."""

from __future__ import annotations

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.config import load_config
from kasm_mcp.server import build_server


def main() -> None:
    config = load_config()
    client = KasmAPIClient(config.api_url, config.api_key, config.api_secret)
    server = build_server(client, config)
    server.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pip install -q -e ".[dev]" && .venv/bin/pytest tests/test_server_scoped_tools.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/server.py src/kasm_mcp/__main__.py tests/test_server_scoped_tools.py
git commit -m "feat: scoped-mode MCP tools (session lifecycle, share, screenshot, exec)"
```

---

## Task 8: SSH-backed exec (optional)

**Files:**
- Create: `src/kasm_mcp/ssh/__init__.py`
- Create: `src/kasm_mcp/ssh/exec_backend.py`
- Modify: `src/kasm_mcp/server.py`
- Test: `tests/test_ssh_exec_backend.py`
- Test: `tests/test_server_ssh_tool.py`

**Interfaces:**
- Consumes: `KasmConfig` (Task 2)
- Produces: `SSHNotConfiguredError`, `resolve_ssh_host(*, explicit_host, override, container_ip) -> str`, `async def ssh_exec(*, host, port, username, key_path, command, working_dir=None, timeout=30.0) -> dict` (`{"stdout": str, "stderr": str, "exit_code": int}`); `build_server` additionally registers `execute_kasm_command_ssh` when `config.ssh_enabled`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ssh_exec_backend.py
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
    mock_connect.assert_awaited_once()
    _, kwargs = mock_connect.call_args
    assert kwargs["username"] == "kasm-user"
    assert kwargs["client_keys"] == ["/key"]
    assert kwargs["known_hosts"] is None
```

```python
# tests/test_server_ssh_tool.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pip install -q asyncssh && .venv/bin/pytest tests/test_ssh_exec_backend.py tests/test_server_ssh_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.ssh'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/ssh/__init__.py
```

```python
# src/kasm_mcp/ssh/exec_backend.py
"""Optional SSH-backed exec: the only way this project can return real
stdout/stderr/exit_code, since the Kasm Developer API's exec_command_kasm
never does. Only reachable when the caller's network can reach the target
host (same Docker network for a container_ip, or a routable override)."""

from __future__ import annotations

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
    full_command = f"cd {working_dir!r} && {command}" if working_dir else command
    async with asyncssh.connect(
        host, port=port, username=username, client_keys=[key_path], known_hosts=None
    ) as conn:
        result = await conn.run(full_command, check=False, timeout=timeout)
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_status}
```

Add to `src/kasm_mcp/server.py` (new logic function, and conditional registration inside `build_server`):

```python
# --- add near the other logic functions, after execute_kasm_command_logic ---

async def execute_kasm_command_ssh_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    command: str,
    working_dir: str | None = None,
    ssh_host: str | None = None,
) -> dict:
    from kasm_mcp.ssh.exec_backend import SSHNotConfiguredError, resolve_ssh_host, ssh_exec

    try:
        validate_command(command)
    except SecurityError as e:
        return {"success": False, "error": str(e), "error_type": "security"}

    if not config.ssh_enabled or not config.ssh_key_path:
        return {
            "success": False,
            "error": "SSH exec is not configured (set KASM_SSH_ENABLED=true and KASM_SSH_KEY_PATH).",
            "error_type": "not_configured",
        }

    container_ip: str | None = None
    try:
        status = await client.get_kasm_status(kasm_id=kasm_id, user_id=config.user_id)
        container_ip = status.get("kasm", status).get("container_ip")
    except KasmAPIError:
        pass  # host resolution can still succeed via explicit param/override

    try:
        host = resolve_ssh_host(explicit_host=ssh_host, override=config.ssh_host_override, container_ip=container_ip)
    except SSHNotConfiguredError as e:
        return {"success": False, "error": str(e), "error_type": "not_configured"}

    try:
        result = await ssh_exec(
            host=host, port=22, username=config.ssh_user, key_path=config.ssh_key_path,
            command=command, working_dir=working_dir,
        )
    except Exception as e:  # noqa: BLE001 - surface any transport/auth failure to the caller
        return {"success": False, "error": f"SSH exec failed: {e}"}

    return {"success": True, **result}
```

```python
# --- inside build_server, after the execute_kasm_command tool registration ---

    if config.ssh_enabled:

        @mcp.tool()
        async def execute_kasm_command_ssh(
            kasm_id: str, command: str, working_dir: str | None = None, ssh_host: str | None = None
        ) -> dict:
            """Run a command via SSH and return real stdout/stderr/exit_code.

            Only registered when KASM_SSH_ENABLED=true. Requires the MCP
            server to have network access to the session's host.
            """
            return await execute_kasm_command_ssh_logic(
                client, config, kasm_id=kasm_id, command=command, working_dir=working_dir, ssh_host=ssh_host
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_ssh_exec_backend.py tests/test_server_ssh_tool.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/ssh/ src/kasm_mcp/server.py tests/test_ssh_exec_backend.py tests/test_server_ssh_tool.py
git commit -m "feat: optional SSH-backed exec with real stdout/exit_code"
```

---

## Task 9: Official admin (user/group) tools

**Files:**
- Modify: `src/kasm_mcp/api/client.py`
- Modify: `src/kasm_mcp/server.py`
- Test: `tests/test_api_client_admin.py`
- Test: `tests/test_server_admin_tools.py`

**Interfaces:**
- Consumes: `KasmAPIClient` (Tasks 5-6)
- Produces: client additions `create_user`, `update_user`, `delete_user`, `get_user`, `get_users`, `logout_user`, `add_user_to_group`, `remove_user_from_group`; `build_server` registers `create_kasm_user`, `update_kasm_user`, `delete_kasm_user`, `get_kasm_user`, `get_kasm_users`, `logout_kasm_user`, `add_user_to_group`, `remove_user_from_group` only when `config.admin_mode`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_client_admin.py
import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.api.client import KasmAPIClient

API_URL = "https://kasm.example.com"


@pytest.fixture
async def client():
    c = KasmAPIClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_create_user_sends_expected_fields(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/create_user", payload={"user": {"user_id": "u1"}})
        result = await client.create_user(username="bob", password="pw", first_name="Bob", last_name="X")
    assert result["user"]["user_id"] == "u1"
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/public/create_user"))][0].kwargs["json"]
    assert sent["target_user"]["username"] == "bob"
    assert sent["target_user"]["password"] == "pw"


@pytest.mark.asyncio
async def test_get_user_by_id(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/get_user", payload={"user": {"user_id": "u1"}})
        result = await client.get_user(user_id="u1")
    assert result["user"]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_add_user_to_group_and_remove(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/public/add_user_group", payload={})
        m.post(f"{API_URL}/api/public/remove_user_group", payload={})
        await client.add_user_to_group(user_id="u1", group_id="g1")
        await client.remove_user_from_group(user_id="u1", group_id="g1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_client_admin.py -v`
Expected: FAIL with `AttributeError: 'KasmAPIClient' object has no attribute 'create_user'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/kasm_mcp/api/client.py` (inside `KasmAPIClient`, after `get_images`):

```python
    # -- Official admin endpoints (require an API key with User/Group management
    # permissions; only wired into server.py when KASM_ADMIN_MODE=true) --

    async def create_user(
        self, *, username: str, password: str, first_name: str = "", last_name: str = "", group_id: str | None = None
    ) -> dict:
        target_user: dict[str, Any] = {"username": username, "password": password, "first_name": first_name, "last_name": last_name}
        data: dict[str, Any] = {"target_user": target_user}
        if group_id:
            data["group_id"] = group_id
        return await self._json("POST", "/api/public/create_user", data)

    async def update_user(self, *, user_id: str, **fields: Any) -> dict:
        target_user = {"user_id": user_id, **fields}
        return await self._json("POST", "/api/public/update_user", {"target_user": target_user})

    async def delete_user(self, *, user_id: str, force: bool = False) -> dict:
        return await self._json("POST", "/api/public/delete_user", {"target_user": {"user_id": user_id}, "force": force})

    async def get_user(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        target_user: dict[str, Any] = {}
        if user_id:
            target_user["user_id"] = user_id
        if username:
            target_user["username"] = username
        return await self._json("POST", "/api/public/get_user", {"target_user": target_user})

    async def get_users(self) -> dict:
        return await self._json("POST", "/api/public/get_users")

    async def logout_user(self, *, user_id: str) -> dict:
        return await self._json("POST", "/api/public/logout_user", {"target_user": {"user_id": user_id}})

    async def add_user_to_group(self, *, user_id: str, group_id: str) -> dict:
        return await self._json("POST", "/api/public/add_user_group", {"target_user": {"user_id": user_id}, "target_group": {"group_id": group_id}})

    async def remove_user_from_group(self, *, user_id: str, group_id: str) -> dict:
        return await self._json("POST", "/api/public/remove_user_group", {"target_user": {"user_id": user_id}, "target_group": {"group_id": group_id}})
```

Add to `tests/test_server_admin_tools.py`:

```python
# tests/test_server_admin_tools.py
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
```

Append to `src/kasm_mcp/server.py` (new logic functions, after `get_available_workspaces_logic`):

```python
_ADMIN_WARNING = "⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments."


async def create_kasm_user_logic(
    client: KasmAPIClient, config: KasmConfig, *, username: str, password: str,
    first_name: str = "", last_name: str = "", group_id: str | None = None,
) -> dict:
    try:
        result = await client.create_user(
            username=username, password=password, first_name=first_name, last_name=last_name, group_id=group_id
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def update_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, **fields: Any) -> dict:
    try:
        result = await client.update_user(user_id=user_id, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def delete_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, force: bool = False) -> dict:
    try:
        await client.delete_user(user_id=user_id, force=force)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id}


async def get_kasm_user_logic(
    client: KasmAPIClient, config: KasmConfig, *, user_id: str | None = None, username: str | None = None
) -> dict:
    try:
        result = await client.get_user(user_id=user_id, username=username)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def get_kasm_users_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_users()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "users": result.get("users", [])}


async def logout_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str) -> dict:
    try:
        await client.logout_user(user_id=user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id}


async def add_user_to_group_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, group_id: str) -> dict:
    try:
        await client.add_user_to_group(user_id=user_id, group_id=group_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id, "group_id": group_id}


async def remove_user_from_group_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, group_id: str) -> dict:
    try:
        await client.remove_user_from_group(user_id=user_id, group_id=group_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id, "group_id": group_id}
```

Append inside `build_server`, right before the final `return mcp` (so it runs after the scoped/SSH blocks already there):

```python
    if config.admin_mode:

        @mcp.tool()
        async def create_kasm_user(
            username: str, password: str, first_name: str = "", last_name: str = "", group_id: str | None = None
        ) -> dict:
            f"""{_ADMIN_WARNING} Create a new Kasm user."""
            return await create_kasm_user_logic(
                client, config, username=username, password=password,
                first_name=first_name, last_name=last_name, group_id=group_id,
            )

        @mcp.tool()
        async def update_kasm_user(user_id: str, **fields: Any) -> dict:
            f"""{_ADMIN_WARNING} Update fields on an existing Kasm user."""
            return await update_kasm_user_logic(client, config, user_id=user_id, **fields)

        @mcp.tool()
        async def delete_kasm_user(user_id: str, force: bool = False) -> dict:
            f"""{_ADMIN_WARNING} Delete a Kasm user."""
            return await delete_kasm_user_logic(client, config, user_id=user_id, force=force)

        @mcp.tool()
        async def get_kasm_user(user_id: str | None = None, username: str | None = None) -> dict:
            f"""{_ADMIN_WARNING} Look up a Kasm user by id or username."""
            return await get_kasm_user_logic(client, config, user_id=user_id, username=username)

        @mcp.tool()
        async def get_kasm_users() -> dict:
            f"""{_ADMIN_WARNING} List all Kasm users."""
            return await get_kasm_users_logic(client, config)

        @mcp.tool()
        async def logout_kasm_user(user_id: str) -> dict:
            f"""{_ADMIN_WARNING} Force-logout a Kasm user's active sessions."""
            return await logout_kasm_user_logic(client, config, user_id=user_id)

        @mcp.tool()
        async def add_user_to_group(user_id: str, group_id: str) -> dict:
            f"""{_ADMIN_WARNING} Add a user to a Kasm group."""
            return await add_user_to_group_logic(client, config, user_id=user_id, group_id=group_id)

        @mcp.tool()
        async def remove_user_from_group(user_id: str, group_id: str) -> dict:
            f"""{_ADMIN_WARNING} Remove a user from a Kasm group."""
            return await remove_user_from_group_logic(client, config, user_id=user_id, group_id=group_id)
```

Note: this requires `from typing import Any` already present at the top of `server.py` (it is, per Task 7's `get_session_screenshot_logic` usage) — no new import needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_api_client_admin.py tests/test_server_admin_tools.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/api/client.py src/kasm_mcp/server.py tests/test_api_client_admin.py tests/test_server_admin_tools.py
git commit -m "feat: opt-in admin-mode user/group management tools"
```

---

## Task 10: Unofficial admin-panel module (registries/images)

**Files:**
- Create: `src/kasm_mcp/admin_unofficial/__init__.py`
- Create: `src/kasm_mcp/admin_unofficial/client.py`
- Modify: `src/kasm_mcp/server.py`
- Test: `tests/test_admin_unofficial_client.py`
- Test: `tests/test_server_unofficial_tools.py`

**Interfaces:**
- Consumes: `request_json` from `api/http.py` (Task 4)
- Produces: `KasmUnofficialAdminClient` with `get_registries()`, `create_registry(*, url, username=None, password=None)`, `delete_registry(*, registry_id)`, `create_workspace_image(*, image_name, friendly_name, **fields)`, `update_workspace_image(*, image_id, **fields)`, `delete_workspace_image(*, image_id)`; `build_server` registers matching tools only when `config.unofficial_api`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin_unofficial_client.py
import aiohttp
import pytest
from aioresponses import aioresponses

from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient

API_URL = "https://kasm.example.com"


@pytest.fixture
async def client():
    c = KasmUnofficialAdminClient(API_URL, "key", "secret")
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_get_registries_hits_admin_path(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/get_registries", payload={"registries": []})
        result = await client.get_registries()
    assert result == {"registries": []}


@pytest.mark.asyncio
async def test_create_registry_sends_target_registry(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/create_registry", payload={"registry": {"registry_id": "r1"}})
        await client.create_registry(url="registry.example.com", username="u", password="p")
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/admin/create_registry"))][0].kwargs["json"]
    assert sent["target_registry"]["url"] == "registry.example.com"


@pytest.mark.asyncio
async def test_create_workspace_image_sends_target_image(client):
    with aioresponses() as m:
        m.post(f"{API_URL}/api/admin/create_image", payload={"image": {"image_id": "i1"}})
        await client.create_workspace_image(image_name="kasmweb/kali-rolling:1.0", friendly_name="Kali")
    sent = m.requests[("POST", aiohttp.client.URL(f"{API_URL}/api/admin/create_image"))][0].kwargs["json"]
    assert sent["target_image"]["image_name"] == "kasmweb/kali-rolling:1.0"
    assert sent["target_image"]["friendly_name"] == "Kali"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_admin_unofficial_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kasm_mcp.admin_unofficial'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/kasm_mcp/admin_unofficial/__init__.py
```

```python
# src/kasm_mcp/admin_unofficial/client.py
"""Wrapper for Kasm's undocumented ``/api/admin/*`` endpoints.

Per Kasm's own "Using Undocumented APIs" support guidance, these accept the
SAME api_key/api_key_secret auth as the documented ``/api/public/*``
endpoints — no admin username/password needed. Endpoint names below are
Kasm's confirmed naming convention (mirroring documented siblings like
create_group/get_images) but are NOT officially documented; verify against
a live instance before relying on them, and expect they may change on any
Kasm upgrade. See docs/ADMIN_UNOFFICIAL.md.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from kasm_mcp.api.http import request_json


class KasmUnofficialAdminClient:
    def __init__(self, api_url: str, api_key: str, api_secret: str) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _json(self, path: str, data: dict[str, Any] | None = None) -> dict:
        return await request_json(
            self._get_session(), self._api_url, self._api_key, self._api_secret, "POST", path, data
        )

    async def get_registries(self) -> dict:
        return await self._json("/api/admin/get_registries")

    async def create_registry(self, *, url: str, username: str | None = None, password: str | None = None) -> dict:
        target_registry: dict[str, Any] = {"url": url}
        if username:
            target_registry["username"] = username
        if password:
            target_registry["password"] = password
        return await self._json("/api/admin/create_registry", {"target_registry": target_registry})

    async def delete_registry(self, *, registry_id: str) -> dict:
        return await self._json("/api/admin/delete_registry", {"target_registry": {"registry_id": registry_id}})

    async def create_workspace_image(self, *, image_name: str, friendly_name: str, **fields: Any) -> dict:
        target_image = {"image_name": image_name, "friendly_name": friendly_name, **fields}
        return await self._json("/api/admin/create_image", {"target_image": target_image})

    async def update_workspace_image(self, *, image_id: str, **fields: Any) -> dict:
        target_image = {"image_id": image_id, **fields}
        return await self._json("/api/admin/update_image", {"target_image": target_image})

    async def delete_workspace_image(self, *, image_id: str) -> dict:
        return await self._json("/api/admin/delete_image", {"target_image": {"image_id": image_id}})
```

Add to `tests/test_server_unofficial_tools.py`:

```python
# tests/test_server_unofficial_tools.py
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
```

Add near the top of `src/kasm_mcp/server.py` (with the other imports):

```python
from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient
```

Append new logic functions, after `remove_user_from_group_logic`:

```python
_UNOFFICIAL_WARNING = "⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true."


async def get_registries_logic(unofficial_client: KasmUnofficialAdminClient) -> dict:
    try:
        result = await unofficial_client.get_registries()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registries": result.get("registries", [])}


async def create_registry_logic(
    unofficial_client: KasmUnofficialAdminClient, *, url: str, username: str | None = None, password: str | None = None
) -> dict:
    try:
        result = await unofficial_client.create_registry(url=url, username=username, password=password)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registry": result.get("registry")}


async def delete_registry_logic(unofficial_client: KasmUnofficialAdminClient, *, registry_id: str) -> dict:
    try:
        await unofficial_client.delete_registry(registry_id=registry_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registry_id": registry_id}


async def create_workspace_image_logic(
    unofficial_client: KasmUnofficialAdminClient, *, image_name: str, friendly_name: str, **fields: Any
) -> dict:
    try:
        result = await unofficial_client.create_workspace_image(image_name=image_name, friendly_name=friendly_name, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image": result.get("image")}


async def update_workspace_image_logic(unofficial_client: KasmUnofficialAdminClient, *, image_id: str, **fields: Any) -> dict:
    try:
        result = await unofficial_client.update_workspace_image(image_id=image_id, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image": result.get("image")}


async def delete_workspace_image_logic(unofficial_client: KasmUnofficialAdminClient, *, image_id: str) -> dict:
    try:
        await unofficial_client.delete_workspace_image(image_id=image_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image_id": image_id}
```

Append inside `build_server`, right before the final `return mcp` (after the `if config.admin_mode:` block already there):

```python
    if config.unofficial_api:
        unofficial_client = KasmUnofficialAdminClient(config.api_url, config.api_key, config.api_secret)

        @mcp.tool()
        async def get_registries() -> dict:
            f"""{_UNOFFICIAL_WARNING} List configured Docker registries."""
            return await get_registries_logic(unofficial_client)

        @mcp.tool()
        async def create_registry(url: str, username: str | None = None, password: str | None = None) -> dict:
            f"""{_UNOFFICIAL_WARNING} Register a Docker registry."""
            return await create_registry_logic(unofficial_client, url=url, username=username, password=password)

        @mcp.tool()
        async def delete_registry(registry_id: str) -> dict:
            f"""{_UNOFFICIAL_WARNING} Delete a configured Docker registry."""
            return await delete_registry_logic(unofficial_client, registry_id=registry_id)

        @mcp.tool()
        async def create_workspace_image(image_name: str, friendly_name: str, **fields: Any) -> dict:
            f"""{_UNOFFICIAL_WARNING} Register a new workspace image."""
            return await create_workspace_image_logic(unofficial_client, image_name=image_name, friendly_name=friendly_name, **fields)

        @mcp.tool()
        async def update_workspace_image(image_id: str, **fields: Any) -> dict:
            f"""{_UNOFFICIAL_WARNING} Update an existing workspace image's fields."""
            return await update_workspace_image_logic(unofficial_client, image_id=image_id, **fields)

        @mcp.tool()
        async def delete_workspace_image(image_id: str) -> dict:
            f"""{_UNOFFICIAL_WARNING} Delete a workspace image."""
            return await delete_workspace_image_logic(unofficial_client, image_id=image_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/pytest tests/test_admin_unofficial_client.py tests/test_server_unofficial_tools.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add src/kasm_mcp/admin_unofficial/ src/kasm_mcp/server.py tests/test_admin_unofficial_client.py tests/test_server_unofficial_tools.py
git commit -m "feat: opt-in unofficial admin-panel module (registries, workspace images)"
```

- [ ] **Step 6: Manually verify unofficial endpoints against the live Kasm instance**

Using the already-configured live credentials (from this session's `.kasm-pentest.env`), run a short interactive Python check for the read-only call only:

```bash
cd /home/ekaracar/kasm-workspaces-mcp
set -a && source /home/ekaracar/.kasm-pentest.env && set +a
.venv/bin/python3 -c "
import asyncio
from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient
import os

async def main():
    c = KasmUnofficialAdminClient(os.environ['KASM_API_URL'], os.environ['KASM_API_KEY'], os.environ['KASM_API_SECRET'])
    try:
        print(await c.get_registries())
    except Exception as e:
        print('FAILED:', e)
    await c.close()

asyncio.run(main())
"
```

Record the real result (success or the exact error) in `docs/ADMIN_UNOFFICIAL.md` (Task 11) — do not call the mutating endpoints (`create_registry`, `create_workspace_image`, etc.) against the live instance without the user's explicit go-ahead, since they modify real state.

---

## Task 11: Documentation

**Files:**
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/API_BEHAVIOR.md`
- Create: `docs/SECURITY.md`
- Create: `docs/ADMIN_UNOFFICIAL.md`

**Interfaces:**
- Consumes: everything built in Tasks 1-10 (docs describe the real, tested surface — no aspirational claims)
- Produces: no code interface; this is the deliverable a human/LLM reads before using the server.

- [ ] **Step 1: Write README.md**

```markdown
# kasm-workspaces-mcp

An MCP server for managing [Kasm Workspaces](https://www.kasmweb.com/) sessions
from an LLM — create/destroy/pause/resume sessions, screenshot them, dispatch
commands, share view-only links, and (opt-in) manage users/groups/registries.

Written from scratch against the real, live-verified behavior of Kasm's
Developer API — see [docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md) for what
that means in practice and why it matters.

## Install

\`\`\`bash
pip install -e ".[dev]"        # add ".[ssh]" too if you want execute_kasm_command_ssh
\`\`\`

## Configure

Required environment variables:

| Variable | Description |
|---|---|
| `KASM_API_URL` | e.g. `https://kasm.example.com` |
| `KASM_API_KEY` / `KASM_API_SECRET` | from Kasm Admin → Access Management → API Keys |
| `KASM_USER_ID` | the Kasm user this server acts as (UUID, with hyphens) |

Optional:

| Variable | Default | Description |
|---|---|---|
| `KASM_ALLOWED_ROOTS` | `/home/kasm-user` | comma-separated path allowlist |
| `KASM_ADMIN_MODE` | `false` | registers official user/group management tools |
| `KASM_UNOFFICIAL_API` | `false` | registers undocumented registry/image tools |
| `KASM_SSH_ENABLED` | `false` | registers `execute_kasm_command_ssh` |
| `KASM_SSH_KEY_PATH` | — | required if `KASM_SSH_ENABLED=true` |
| `KASM_SSH_USER` | `kasm-user` | |
| `KASM_SSH_HOST_OVERRIDE` | — | use when `container_ip` isn't reachable from where this server runs |

## Run

\`\`\`bash
kasm-mcp
\`\`\`

Or wire it into a `.mcp.json`:

\`\`\`json
{
  "mcpServers": {
    "kasm": {
      "type": "stdio",
      "command": "kasm-mcp",
      "env": {
        "KASM_API_URL": "https://kasm.example.com",
        "KASM_API_KEY": "...",
        "KASM_API_SECRET": "...",
        "KASM_USER_ID": "..."
      }
    }
  }
}
\`\`\`

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module map and data flow
- [docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md) — verified real Kasm API quirks
- [docs/SECURITY.md](docs/SECURITY.md) — the three opt-in modes and their threat models
- [docs/ADMIN_UNOFFICIAL.md](docs/ADMIN_UNOFFICIAL.md) — the undocumented registry/image module

## License

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 2: Write docs/ARCHITECTURE.md**

```markdown
# Architecture

## Module map

\`\`\`
config.py              env vars -> KasmConfig (fail-fast validation)
security/validation.py command/path injection checks
api/http.py             shared authenticated HTTP (request_json, request_binary)
api/client.py           KasmAPIClient -- /api/public/* (scoped + admin-official)
admin_unofficial/       KasmUnofficialAdminClient -- /api/admin/* (same auth, undocumented)
ssh/exec_backend.py     optional real-output exec, independent of the Developer API
server.py               plain async "logic" functions + build_server() FastMCP wiring
__main__.py             load_config() -> build_server() -> run()
\`\`\`

## Data flow

\`\`\`
MCP client (e.g. Claude Code)
   |
   v
server.py tool (FastMCP-decorated closure)
   |
   v
server.py logic function (client, config, **kwargs) -> dict
   |
   +---> api/client.py (KasmAPIClient)  ---> api/http.py ---> Kasm /api/public/*
   |
   +---> admin_unofficial/client.py     ---> api/http.py ---> Kasm /api/admin/*  (unofficial_api=true only)
   |
   +---> ssh/exec_backend.py            ---> asyncssh    ---> session container directly (ssh_enabled=true only)
\`\`\`

Every external call returns through the same `{"success": bool, ...}` shape
so an LLM caller has one consistent pattern to branch on, whether the
underlying failure was a Kasm API error, a security-validation rejection,
or (for SSH) a transport failure.

## Why logic functions are separate from `@mcp.tool()` closures

`build_server(client, config)` constructs a fresh `FastMCP` instance and
defines each tool as a thin closure that just calls a plain async
function. Tests call those plain functions directly with a mocked
`KasmAPIClient` — no MCP protocol machinery involved, so tests run in
milliseconds and failures point straight at the logic, not the transport.

## Extension points

- **New Developer API method:** add it to `api/client.py`, add a logic
  function + `@mcp.tool()` closure in `server.py`.
- **New scoped vs. gated tool:** scoped tools register unconditionally in
  `build_server`; admin/unofficial/ssh tools register inside their
  respective `if config.X:` block — follow that pattern, don't add a new
  gating mechanism.
- **New undocumented admin-panel endpoint:** add it to
  `admin_unofficial/client.py`, verify it live per the process in
  `docs/ADMIN_UNOFFICIAL.md` before trusting its shape in a fixture.
```

- [ ] **Step 3: Write docs/API_BEHAVIOR.md**

```markdown
# Verified Kasm Developer API behavior

Everything below was confirmed live against a real Kasm instance during
this project's design phase — not assumed from the official docs alone,
which are incomplete or silent on several of these points.

## `exec_command_kasm` is fire-and-forget

The response never contains stdout/stderr/exit_code — Kasm's own official
docs' example response is just `{"kasm": {...}, "current_time": "..."}`.
`execute_kasm_command` in this project reflects that honestly: success
only means "dispatched," never "ran successfully with this output." Use
`execute_kasm_command_ssh` (opt-in) if you need real output.

## `get_kasm_screenshot` returns raw JPEG bytes, not JSON

Calling `.json()` on the response crashes; `api/http.py`'s `request_binary`
checks content-type and reads raw bytes instead.

## `share_id` is `null` unless you pass `enable_sharing: true`

`request_kasm`'s response always includes a `share_id` field, but it's
`null` by default. Passing `enable_sharing: true` in the request body
populates it, at which point `join_kasm` can turn it into a usable
(view-only, by default) join link.

## Required API-key permissions

| Operation | Permission(s) needed |
|---|---|
| `request_kasm`, `get_kasm_status`, `exec_command_kasm` | `User` + `Users Auth Session` |
| `get_kasms` / `get_user_kasms` (listing) | `Sessions View` |
| `exec_command_kasm` command modification | `Sessions Modify` |

A 403 from the Kasm API on session creation almost always means the API
key is missing `User` and/or `Users Auth Session`, not a code bug.

## `join_kasm` links are view-only by default

The joining viewer gets no mouse/keyboard control unless the Kasm group's
`shared_session_full_control` setting (Admin → Groups → your group →
Session Settings, default `false`) is enabled. There's no API parameter
to request full control per-link — it's a group-wide setting.

## `/api/admin/*` accepts the same API-key auth as `/api/public/*`

Confirmed via Kasm's own "Using Undocumented APIs" support article: swap
the URL prefix, same `api_key`/`api_key_secret` body fields. No admin
username/password needed. See `docs/ADMIN_UNOFFICIAL.md`.
```

- [ ] **Step 4: Write docs/SECURITY.md**

```markdown
# Security model

Three independent opt-in flags, each `false` by default:

## Scoped mode (always on)

Acts only as the single pre-provisioned `KASM_USER_ID`. Cannot create,
delete, or modify other users. This is the recommended default for any
shared or production-adjacent Kasm deployment: give the LLM a
purpose-built, low-privilege Kasm user and API key, and it can never do
more than that user could do by hand.

## `KASM_ADMIN_MODE=true`

Registers official `/api/public/*` user/group management tools
(create/update/delete user, group membership). Requires an API key with
User Management permissions. Every such tool's docstring warns: not
recommended for shared or production Kasm deployments — a compromised or
misdirected LLM session could create, modify, or delete real user
accounts.

## `KASM_UNOFFICIAL_API=true`

Registers registry/workspace-image management tools against Kasm's
undocumented `/api/admin/*` endpoints. Same API-key auth as above (no
extra credential), but:

- Not officially supported by Kasm; may change or break on any upgrade.
- Broader blast radius: can add/remove Docker registries and workspace
  image definitions server-wide, not just user-scoped state.

Enable only against a Kasm instance you're comfortable experimenting
against.

## `KASM_SSH_ENABLED=true`

Registers `execute_kasm_command_ssh`. Requires an SSH private key
(`KASM_SSH_KEY_PATH`) and network reachability to the session container.
This bypasses the Kasm API entirely for that one call — treat the SSH
key with the same care as the Kasm API secret (never log it, never pass
it as a command-line argument).

## General rules (apply regardless of mode)

- Secrets come only from environment/files, never from tool-call
  arguments, and are never logged.
- `execute_kasm_command` and `execute_kasm_command_ssh` both run their
  `command` argument through `security/validation.py` before dispatch —
  shell metacharacters (`| ; && || \` $( $\{ >> > <`) are rejected, not
  escaped, forcing callers to use a pre-written script file for anything
  beyond a single plain command.
```

- [ ] **Step 5: Write docs/ADMIN_UNOFFICIAL.md**

```markdown
# Unofficial admin-panel module

`admin_unofficial/client.py` calls Kasm's internal `/api/admin/*`
endpoints — the same ones the Kasm web admin panel itself uses. Kasm's
own "Using Undocumented APIs" support article confirms these accept the
same `api_key`/`api_key_secret` auth as the documented `/api/public/*`
endpoints (open the admin panel's network tab, perform the action, note
the `/api/admin/<name>` path, swap the prefix — no username/password
needed).

## What's implemented

`get_registries`, `create_registry`, `delete_registry`,
`create_workspace_image`, `update_workspace_image`,
`delete_workspace_image`.

## Verification status

- `get_registries`: [fill in with the Task 10 Step 6 result — record the
  exact response or error observed against the live instance here]
- The mutating endpoints (`create_registry`, `delete_registry`,
  `create_workspace_image`, `update_workspace_image`,
  `delete_workspace_image`) have **not** been called against a live
  instance — their request/response shapes follow Kasm's confirmed naming
  convention (`target_registry`/`target_image` wrapper objects, matching
  `target_user` in the official user-management endpoints) but are
  unverified. Confirm each one manually (dry run against a disposable
  registry/image first) before depending on it.

## Risk

This entire module can break on any Kasm version upgrade with no notice,
since none of it is part of Kasm's supported public contract. Don't
depend on it for anything you can't tolerate failing silently-differently
after a Kasm update.
```

- [ ] **Step 6: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add README.md docs/ARCHITECTURE.md docs/API_BEHAVIOR.md docs/SECURITY.md docs/ADMIN_UNOFFICIAL.md
git commit -m "docs: README, architecture, verified API behavior, security model"
```

---

## Task 12: CI and packaging polish

**Files:**
- Create: `.github/workflows/ci.yml`
- Test: manual smoke test (no new pytest file — this task verifies the *packaging*, not new logic)

**Interfaces:**
- Consumes: everything from Tasks 1-11
- Produces: a GitHub Actions workflow; a verified `kasm-mcp --help`-equivalent smoke path.

- [ ] **Step 1: Write the failing check**

There's no new logic to TDD here; the "test" is that CI config is valid and the full suite passes locally exactly as CI would run it:

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/ruff check src tests; .venv/bin/mypy src; .venv/bin/pytest -v`
Expected: at this point (before `ruff`/`mypy` are configured against the real codebase) this may show lint/type warnings — note them, they'll be fixed in Step 3.

- [ ] **Step 2: (no separate failing-test step — this task fixes what Step 1 surfaces)**

- [ ] **Step 3: Write the CI workflow and fix any lint/type issues Step 1 surfaced**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev,ssh]"
      - run: ruff check src tests
      - run: mypy src
      - run: pytest -v
```

Fix whatever `ruff`/`mypy` flagged in Step 1 directly in the affected files from Tasks 1-11 (e.g. missing return type annotations, unused imports) — these are small, targeted edits, not new features.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ekaracar/kasm-workspaces-mcp && .venv/bin/ruff check src tests && .venv/bin/mypy src && .venv/bin/pytest -v`
Expected: PASS, zero lint/type errors, full test suite green

- [ ] **Step 5: Verify the installed console script works end-to-end (config-validation path only — no real network)**

Run:
```bash
cd /home/ekaracar/kasm-workspaces-mcp
.venv/bin/pip install -q -e .
KASM_API_URL=x .venv/bin/kasm-mcp 2>&1 | head -5
```
Expected: a clear `ConfigError` message about missing `KASM_API_KEY` (proves the console script entry point resolves and config validation runs before anything network-related) — not a traceback about the import path or entry point being wrong.

- [ ] **Step 6: Commit**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
git add .github/workflows/ci.yml
git add -u  # any lint/type fixes made to existing files
git commit -m "ci: GitHub Actions workflow (pytest, ruff, mypy)"
```

---

## Task 13: Publish to GitHub

**Files:** none (repo operations only)

**Interfaces:** none — this task ships Tasks 1-12's already-committed local repo.

- [ ] **Step 1: Confirm with the user before creating anything on GitHub or pushing**

This step is a hard stop: per the standing git-safety rules, creating a
remote repo and pushing are both "visible to others / affects shared
state" actions. Ask explicitly: repo visibility (private recommended,
given this manages real infrastructure credentials via env vars even
though none are committed) and confirm the name `kasm-workspaces-mcp`
under the `erkankrcr` account. Do not proceed to Step 2 without an
explicit yes.

- [ ] **Step 2: Create the GitHub repo and push**

```bash
cd /home/ekaracar/kasm-workspaces-mcp
gh repo create erkankrcr/kasm-workspaces-mcp --private --source=. --remote=origin
git push -u origin master
```

- [ ] **Step 3: Verify**

Run: `gh repo view erkankrcr/kasm-workspaces-mcp --json name,visibility,url`
Expected: JSON confirming the repo exists with the intended visibility, and `git log origin/master -1` matches the local `master` HEAD.

---

## Explicitly deferred (next phase, not this plan)

Rewriting `erkankrcr/kasm-pentest`'s `SKILL.md` and `.mcp.json` to point at
this new server and describe its real (not assumed) tool behavior — a
separate follow-on task once this repo is implemented and working, per
the design spec §7.
