# kasm-workspaces-mcp

An MCP server for managing [Kasm Workspaces](https://www.kasmweb.com/) sessions
from an LLM — create/destroy/pause/resume sessions, screenshot them, dispatch
commands, share view-only links, and (opt-in) manage users/groups/registries.

Written from scratch against the real, live-verified behavior of Kasm's
Developer API — see [docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md) for what
that means in practice and why it matters.

## Install

```bash
pip install -e ".[dev]"        # add ".[ssh]" too if you want execute_kasm_command_ssh
```

## Configure

Required environment variables:

| Variable | Description |
|---|---|
| `KASM_API_URL` | e.g. `https://kasm.example.com` |
| `KASM_API_KEY` / `KASM_API_SECRET` | from Kasm Admin → Access Management → API Keys (some versions: Settings → Developers) |
| `KASM_USER_ID` | the Kasm user this server acts as (UUID, with hyphens) |

**API keys have no permissions by default** — on the key's own *Permissions*
tab (not a role label shown elsewhere in the UI), grant at minimum `User`,
`Users Auth Session`, `Sessions View`, `Sessions Modify`, `Images View` to
cover this server's default tools. Full per-endpoint breakdown, including
`KASM_ADMIN_MODE`/`KASM_UNOFFICIAL_API` tools: [docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md#required-api-key-permissions).

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
| `KASM_ENABLE_WORKSPACE_REGISTRY` | **`true`** | registers `connect_workspace` (find-by-name, auto-create/reuse session, run a command — see below). On by default — it's the whole point of this server, and costs nothing when idle (no background process, just a local SQLite file touched only when the tool is called). Set to `false` to turn it off. |
| `KASM_DB_PATH` | `~/.local/state/kasm-workspaces-mcp/registry.db` | local SQLite cache/state file used by `connect_workspace` |

Enabling (or changing) a flag only takes effect after the MCP client
reconnects to this server — e.g. Claude Code's `/mcp` command, or a
restart.

Any of these can also go in a `.env` file in the directory you run `kasm-mcp`
from (see `.env.example`) — it's loaded automatically and never overrides a
variable already set in the real environment (e.g. by an MCP client's own
`env` config in `.mcp.json`).

## Debugging permission errors

If any tool call fails with `"Unauthorized"`, ask the LLM to run
**`diagnose_permissions`** (registered by default, no setup needed). It
probes every permission this server needs — `Images View`, `Sessions
View`, `Users View`, `User` + `Users Auth Session`, `Sessions Modify` —
using only safe, non-mutating calls (nothing is created, changed, or
destroyed) and reports exactly which one(s) are missing, plus where to
fix them in the Kasm admin UI. See
[docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md#required-api-key-permissions)
for the full per-endpoint permission table this is built from.

## Run

```bash
kasm-mcp
```

Or wire it into a `.mcp.json`:

```json
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
```

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module map and data flow
- [docs/API_BEHAVIOR.md](docs/API_BEHAVIOR.md) — verified real Kasm API quirks
- [docs/SECURITY.md](docs/SECURITY.md) — the three opt-in modes and their threat models
- [docs/ADMIN_UNOFFICIAL.md](docs/ADMIN_UNOFFICIAL.md) — the undocumented registry/image module

## License

MIT — see [LICENSE](LICENSE).
