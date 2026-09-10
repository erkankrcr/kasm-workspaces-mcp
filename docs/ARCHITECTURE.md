# Architecture

## Module map

```
config.py              env vars -> KasmConfig (fail-fast validation)
security/validation.py command/path injection checks
api/http.py             shared authenticated HTTP (request_json, request_binary)
api/client.py           KasmAPIClient -- /api/public/* (scoped + admin-official)
admin_unofficial/       KasmUnofficialAdminClient -- /api/admin/* (same auth, undocumented)
ssh/exec_backend.py     optional real-output exec, independent of the Developer API
server.py               plain async "logic" functions + build_server() FastMCP wiring
__main__.py             load_config() -> build_server() -> run()
```

## Data flow

```
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
```

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
