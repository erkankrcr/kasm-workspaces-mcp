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
