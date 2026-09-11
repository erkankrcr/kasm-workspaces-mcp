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
- `create_registry`/`delete_registry` have **not** been called against a
  live instance — unverified, confirm manually first.
- **`create_workspace_image` was tested live 2026-09-11 (creating a real
  "Kali Linux" image entry) and confirmed working, with caveats:**
  - The field is `name` (matching what `get_images()` returns), **not**
    `image_name` — same mistake class as the `request_kasm` bug in
    `docs/API_BEHAVIOR.md`. Sending `image_name` doesn't error; Kasm just
    silently leaves the image's `name` as `null` (unusable — undetectable
    without checking the response). Fixed in this client 2026-09-11.
  - `docker_registry`, `server_id`, `restrict_to_server`, `cores`,
    `memory_bytes`, `description` all work fine in `create_image`.
  - **`available`, `categories`, and `default_category` crash
    `create_image` with a bare `HTTP 500 <H1>Internal Error</H1>`** on
    that live instance — a Kasm-side bug, confirmed by bisecting fields
    one at a time. This client now rejects them client-side with a clear
    `ValueError` instead of forwarding to a confusing raw 500.
  - Without `available: true`, the created image can't be scheduled —
    `request_kasm` against it fails with `"No resources are available to
    create the requested Kasm."` (not a permissions error; Kasm just
    won't launch an image it doesn't consider available).
  - `update_workspace_image` returned `403 Unauthorized` on that same
    key — even though it could create/delete images, it apparently
    lacks whatever permission `update_image` needs (untested which one;
    try granting `Images Modify` on the key's Permissions tab first).
  - **Net result:** creating a new workspace image via this API works,
    but flipping it to actually launchable currently requires a manual
    step in the Kasm admin UI (toggle "Available" on the image) — there
    is no known working API path to do that toggle yet on this Kasm
    version.
- `delete_workspace_image` was exercised repeatedly during the above
  testing (cleaning up broken/intermediate image records) and worked
  every time — confirmed live.

## Risk

This entire module can break on any Kasm version upgrade with no notice,
since none of it is part of Kasm's supported public contract. Don't
depend on it for anything you can't tolerate failing silently-differently
after a Kasm update.
