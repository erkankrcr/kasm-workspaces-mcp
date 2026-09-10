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

Any of these can also go in a `.env` file in the directory you run `kasm-mcp`
from (see `.env.example`) — it's loaded automatically and never overrides a
variable already set in the real environment (e.g. by an MCP client's own
`env` config in `.mcp.json`).

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
