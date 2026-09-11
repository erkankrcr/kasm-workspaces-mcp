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

## `request_kasm` requires `image_id`, not `image_name`

The request body field is `image_id` (the image's hash-like id from
`get_images`, e.g. `1d3fa23be2fd4031a2c3dea0f9f6713e`) — not a docker image
name or friendly name. Sending `image_name` instead is silently ignored:
Kasm falls back to looking for a "default" image for the group and fails
with `"No Default Image Found"` regardless of the value or the group_id
used. This cost real debugging time (2026-09-11) before being confirmed
live via direct API calls. `create_kasm_session` and `connect_workspace`
resolve a human-friendly `image`/`identifier` string to the correct
`image_id` themselves (see `kasm_mcp/api/resolution.py`) — callers should
never need to pass a raw image_id by hand.

## `share_id` is `null` unless you pass `enable_sharing: true`

`request_kasm`'s response always includes a `share_id` field, but it's
`null` by default. Passing `enable_sharing: true` in the request body
populates it, at which point `join_kasm` can turn it into a usable
(view-only, by default) join link.

## Required API-key permissions

**Don't diagnose this by hand — ask the LLM to run the `diagnose_permissions`
tool first.** It runs the safe, non-mutating probes below for you and
reports exactly which permission(s) are missing.

**Configure at: Settings → Developers → edit the API key → Permissions tab.**
Per Kasm's own docs: *"By default, API keys have no permissions."* A
label like "Global Admin" shown elsewhere in the admin UI (e.g. on the
admin *user account* that owns the key) is **not** the same thing as
this key's own Permissions tab — confirmed live on 2026-09-11: a key
whose owning account showed "Global Admin" still got `403 Unauthorized`
on `request_kasm`/`get_kasm_status` until `Users Auth Session` was
granted on the key itself.

Full table, cross-referenced from the official Kasm Developer API docs
(<https://www.kasmweb.com/docs/latest/developers/developer_api.html>)
against every endpoint this project actually calls:

| Endpoint(s) used by this project | Required permission(s) |
|---|---|
| `request_kasm`, `get_kasm_status`, `destroy_kasm`, `join_kasm` | `User` + `Users Auth Session` |
| `exec_command_kasm` | `Sessions Modify` (and, per the pattern above, likely `User` + `Users Auth Session` too — not separately confirmed live) |
| `pause_kasm`, `resume_kasm`, `get_kasm_screenshot` | Not individually documented; same session-lifecycle family as the row above — provision `User` + `Users Auth Session` + `Sessions Modify` to cover them |
| `get_kasms` | `Sessions View` |
| `get_images` | `Images View` |
| `get_user`, `get_users` | `Users View` |
| `create_user` | `Users Create` |
| `update_user` | `Users Modify` (+ `Users Modify Admin` if the target is itself a Global Admin) |
| `delete_user` | `Users Delete` + `Users Modify` (+ `Users Modify Admin` if the target is a Global Admin) |
| `logout_user` | `Users Auth Session` |
| `add_user_group`, `remove_user_group` | `Groups Modify` |
| `get_registries`, `create_registry`, `delete_registry` (unofficial admin API) | Live-tested 403 with a key lacking them; Kasm's own docs describe registries access as needing `Images View` + `System View` + `Agents View` |
| `create_workspace_image`, `update_workspace_image`, `delete_workspace_image` (unofficial admin API) | `Images Modify` (untested live — inferred from the naming pattern) |

**Minimum set to run this server's default (non-admin) tools day to day:**
`User`, `Users Auth Session`, `Sessions View`, `Sessions Modify`, `Images View`.

A 403 from the Kasm API on session creation almost always means the API
key is missing `User` and/or `Users Auth Session`, not a code bug —
verify on the key's own Permissions tab, not a role label seen elsewhere.

## `join_kasm` links are view-only by default

The joining viewer gets no mouse/keyboard control unless the Kasm group's
`shared_session_full_control` setting (Admin → Groups → your group →
Session Settings, default `false`) is enabled. There's no API parameter
to request full control per-link — it's a group-wide setting.

## `/api/admin/*` accepts the same API-key auth as `/api/public/*`

Confirmed via Kasm's own "Using Undocumented APIs" support article: swap
the URL prefix, same `api_key`/`api_key_secret` body fields. No admin
username/password needed. See `docs/ADMIN_UNOFFICIAL.md`.
