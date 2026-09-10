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

- `get_registries()` was tested live against a real Kasm instance. Result: HTTP 403 with a clean JSON body `{"error_message": "Unauthorized"}`. This confirms the endpoint path and `api_key`/`api_key_secret` auth mechanism ARE correctly reached and parsed by the server (not a 404, not an HTML error page) — but the test API key lacked the required admin permissions for registries (per Kasm's own docs: "Registries View requires Images View, System View, and Agents View"). The auth *mechanism* this module uses is confirmed correct; a deployment wanting to use this module needs an API key with those specific admin permissions granted.
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
