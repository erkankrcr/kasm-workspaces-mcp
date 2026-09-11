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

# Fields that returned HTTP 500 from /api/admin/create_image on a live Kasm
# instance (2026-09-11), regardless of the correct field name being used —
# a Kasm-side bug, not a client bug. Rejected client-side with a clear error
# instead of letting a raw, unhelpful 500 through.
_CREATE_IMAGE_UNSUPPORTED_FIELDS = {"available", "categories", "default_category"}


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

    async def create_workspace_image(self, *, name: str, friendly_name: str, **fields: Any) -> dict:
        bad = _CREATE_IMAGE_UNSUPPORTED_FIELDS & fields.keys()
        if bad:
            raise ValueError(
                f"create_image crashes (HTTP 500) on a live Kasm instance when given: {sorted(bad)}. "
                "Create without them, then set them afterward via the Kasm admin UI. See "
                "docs/ADMIN_UNOFFICIAL.md."
            )
        target_image = {"name": name, "friendly_name": friendly_name, **fields}
        return await self._json("/api/admin/create_image", {"target_image": target_image})

    async def update_workspace_image(self, *, image_id: str, **fields: Any) -> dict:
        target_image = {"image_id": image_id, **fields}
        return await self._json("/api/admin/update_image", {"target_image": target_image})

    async def delete_workspace_image(self, *, image_id: str) -> dict:
        return await self._json("/api/admin/delete_image", {"target_image": {"image_id": image_id}})
