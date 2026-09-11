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

⚠️ **Backlog / Work In Progress — see `docs/BACKLOG.md`.** This flag
registers a tool that, in most environments, will not actually reach a
session container: it needs both network reachability from this MCP
server to the container (not just the same LAN as the Kasm agent host —
confirmed live 2026-09-11) *and* an SSH daemon running inside the
workspace image (stock `kasmweb/*` images don't have one). Everything
below describes what the flag does and its security tradeoffs *if* you
have both prerequisites — it does not mean the feature is ready for
general use.

Registers `execute_kasm_command_ssh`. Requires an SSH private key
(`KASM_SSH_KEY_PATH`) and network reachability to the session container.
This bypasses the Kasm API entirely for that one call — treat the SSH
key with the same care as the Kasm API secret (never log it, never pass
it as a command-line argument).

**Accepted tradeoff — no host-key verification:** `ssh_exec` connects with
`known_hosts=None`, disabling SSH host-key checking. This is a deliberate
choice, not an oversight: Kasm session containers are ephemeral and get a
fresh host key on every creation, so there's nothing stable to pin
against, and the intended use is a same-Docker-network `container_ip`
that isn't reachable from outside that network anyway. This does mean a
host on the same network path could in principle intercept the
connection (no MITM protection) — acceptable for the stated same-network
use case, but do not point `KASM_SSH_HOST_OVERRIDE` at a host reachable
over an untrusted network without understanding this tradeoff.

## General rules (apply regardless of mode)

- Secrets come only from environment/files, never from tool-call
  arguments, and are never logged.
- `execute_kasm_command` and `execute_kasm_command_ssh` both run their
  `command` argument through `security/validation.py` before dispatch —
  shell metacharacters (`| ; && || \` $( $\{ >> > <`) are rejected, not
  escaped, forcing callers to use a pre-written script file for anything
  beyond a single plain command.
