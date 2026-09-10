# kasm-workspaces-mcp — Design Spec

Status: approved (pending final user sign-off on this written doc)
Date: 2026-09-10

## 1. Motivation

We currently depend on `kasm-mcp-server-v2` (github.com/roguedev-ai, MIT
licensed) as the MCP server that lets an LLM manage Kasm Workspaces
sessions. That repo has two problems:

1. It's someone else's codebase we've been running as-is — we want an
   original implementation we own, not a copy/fork of MIT-licensed code.
2. Empirically (verified live against a real Kasm instance this session)
   its assumptions about the Kasm Developer API are wrong in several
   places, causing silent false-success/false-failure results:
   - `exec_command_kasm` is fire-and-forget — it never returns
     stdout/stderr/exit_code. The old server's `execute_kasm_command`,
     `read_kasm_file`, and `write_kasm_file` all assumed a synchronous
     `exit_code` field that never arrives, so `read_kasm_file` always
     fails and `write_kasm_file` always reports failure even when the
     write likely succeeded.
   - `get_kasm_screenshot` returns a raw JPEG body, not JSON — the old
     server calls `response.json()` on it unconditionally and crashes.
   - `request_kasm`'s `share_id` field is `null` unless the caller
     explicitly passes `enable_sharing: true` — undocumented in the
     old server, so session sharing silently never worked.
   - Session-lifecycle endpoints (`request_kasm`, `get_kasm_status`,
     `exec_command_kasm`) need the `User` + `Users Auth Session` API-key
     permissions; listing (`get_kasms`/`get_user_kasms`) needs
     `Sessions View`. None of this is documented anywhere in the old repo.

This project (`kasm-workspaces-mcp`) is a clean-room rewrite that: (a) is
fully original code we own under our own license, and (b) only claims
behavior we've verified against the real API, documenting the gaps
honestly instead of papering over them.

## 2. Scope

In scope: session lifecycle, sharing, screenshots, best-effort exec,
optional SSH-backed exec with real output capture, read-only workspace
image listing, an opt-in official user/group admin toolset, and an
opt-in experimental unofficial-admin-API toolset (registries/images).

Out of scope: anything requiring Kasm admin **username/password**
login (we only ever use API key + secret, either against
`/api/public/*` or, for the unofficial module, `/api/admin/*` — which
Kasm's own support docs confirm accepts the same API key auth).

## 3. Architecture

```
kasm-workspaces-mcp/
├── src/kasm_mcp/
│   ├── __main__.py            # entrypoint (console_script: kasm-mcp)
│   ├── server.py              # FastMCP tool registration, mode gating
│   ├── config.py              # env var loading + startup validation
│   ├── api/
│   │   ├── client.py          # Kasm Developer API async HTTP client
│   │   └── models.py          # typed response dataclasses
│   ├── ssh/
│   │   └── exec_backend.py    # optional SSH exec (asyncssh)
│   ├── admin_unofficial/
│   │   └── client.py          # /api/admin/* wrapper, same api_key auth
│   └── security/
│       └── validation.py      # command/path injection filtering
├── tests/
│   ├── fixtures/               # real (sanitized) captured API responses
│   └── test_*.py               # pytest + aioresponses, no live server needed
├── docs/
│   ├── ARCHITECTURE.md         # module map, data flow, extension points
│   ├── API_BEHAVIOR.md         # verified real Kasm API quirks (this doc's §1, expanded)
│   ├── SECURITY.md             # scoped vs admin vs unofficial threat model
│   └── ADMIN_UNOFFICIAL.md     # what's reverse-engineered, stability caveat
├── .github/workflows/ci.yml    # pytest + ruff + mypy on push
├── README.md
├── pyproject.toml
└── LICENSE                     # MIT
```

**Data flow:** MCP client (Claude Code) → `server.py` tool call →
`api/client.py` (async HTTP to `/api/public/*`) → Kasm Workspaces
server. The SSH path is parallel and independent: `server.py` →
`ssh/exec_backend.py` (asyncssh) → Kasm session container directly,
bypassing the Developer API entirely for that one call.

**Module boundaries:** `api/client.py` never imports from `ssh/` or
`admin_unofficial/` — those are additive capabilities `server.py` wires
in conditionally based on config flags. Each module can be read and
tested in isolation.

## 4. Tool surface

### Scoped mode (always registered)

| Tool | Notes |
|---|---|
| `create_kasm_session(image_name, group_id, enable_sharing=False)` | |
| `destroy_kasm_session(kasm_id)` | |
| `pause_kasm_session` / `resume_kasm_session` | |
| `get_session_status(kasm_id)` | |
| `list_user_sessions()` | |
| `get_share_link(share_id)` | View-only; documents the `shared_session_full_control` group setting caveat |
| `get_session_screenshot(kasm_id, width?, height?, save_to_file?)` | Correct binary JPEG handling |
| `execute_kasm_command(kasm_id, command, working_dir?, user?)` | Honest "dispatched" response, no fabricated output/exit_code |
| `get_available_workspaces()` | Read-only `get_images` |

### SSH-backed exec (registered only if `KASM_SSH_ENABLED=true`)

| Tool | Notes |
|---|---|
| `execute_kasm_command_ssh(kasm_id, command, working_dir?)` | Real stdout/stderr/exit_code. Host resolution priority: explicit `ssh_host` param → `KASM_SSH_HOST_OVERRIDE` → session's `container_ip` (same-Docker-network only, documented). Auth via `KASM_SSH_KEY_PATH` + `KASM_SSH_USER` (default `kasm-user`). Returns a clear "SSH not configured" error when disabled — never silently falls back to the fire-and-forget path. |

### Admin mode (registered only if `KASM_ADMIN_MODE=true`)

Official `/api/public/*` endpoints for user/group management:
`create_kasm_user`, `update_kasm_user`, `delete_kasm_user`,
`get_kasm_user(s)`, `logout_kasm_user`, `add_user_to_group`,
`remove_user_from_group`. Each tool's docstring carries an explicit
warning: requires an admin-privileged API key; not recommended for
shared/production Kasm deployments.

### Unofficial admin-panel module (registered only if `KASM_UNOFFICIAL_API=true`)

`get_registries`, `create_registry`, `delete_registry`,
`create_workspace_image`, `update_workspace_image`,
`delete_workspace_image` — calling `/api/admin/*` paths with the same
API key auth (per Kasm's own "Using Undocumented APIs" support
guidance). Exact endpoint names/schemas are **not officially
documented**; they will be verified empirically against a live
instance during implementation (read-only calls tried directly,
mutating calls confirmed with the user before first use) rather than
guessed. `docs/ADMIN_UNOFFICIAL.md` states plainly: unofficial,
may break on any Kasm upgrade, use at your own risk.

## 5. Security model

- Three independent opt-in flags, all default `false`:
  `KASM_ADMIN_MODE`, `KASM_UNOFFICIAL_API`, `KASM_SSH_ENABLED`.
- Secrets (`KASM_API_KEY`, `KASM_API_SECRET`, SSH private key) are read
  only from environment/files, never logged, never placed in
  subprocess command-line arguments (lesson learned live this session:
  putting a token in a shell command line is both a real security smell
  and got auto-blocked by Claude Code's own safety classifier).
- Startup fails fast with a clear message if required config is
  missing/malformed, instead of partially starting like the old server.
- `docs/SECURITY.md` documents the threat model for each mode plainly,
  including that admin/unofficial modes should only be enabled against
  a Kasm instance dedicated to this use case, not a shared production one.

## 6. Testing & packaging

- `pytest` + `aioresponses` for the HTTP client — no live Kasm server
  required for CI. `tests/fixtures/` includes real (sanitized) response
  shapes captured this session (e.g. full `get_kasm_status` payload)
  as regression fixtures.
- `ruff` + `mypy` + `pytest` run in GitHub Actions on push.
- `pyproject.toml` (no `requirements.txt`), `src/` layout, console
  script entry point `kasm-mcp`.
- License: MIT.

## 7. Explicitly out of this spec (next phase)

Rewriting `erkankrcr/kasm-pentest`'s `SKILL.md` and `.mcp.json` to
match this new server's real, verified tool surface is a separate
follow-on task, done after this repo is implemented and working.
