"""Async client for the Kasm Developer API (``/api/public/*``).

Every method here implements behavior verified live against a real Kasm
instance this project's design session — see docs/API_BEHAVIOR.md.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from kasm_mcp.api.http import request_binary, request_json


class KasmAPIClient:
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

    async def _json(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict:
        return await request_json(
            self._get_session(), self._api_url, self._api_key, self._api_secret, method, path, data
        )

    async def _binary(self, method: str, path: str, data: dict[str, Any] | None = None) -> bytes:
        return await request_binary(
            self._get_session(), self._api_url, self._api_key, self._api_secret, method, path, data
        )

    async def request_kasm(
        self, *, image_name: str, user_id: str, group_id: str, enable_sharing: bool = False
    ) -> dict:
        data: dict[str, Any] = {"image_name": image_name, "user_id": user_id, "group_id": group_id}
        if enable_sharing:
            data["enable_sharing"] = True
        return await self._json("POST", "/api/public/request_kasm", data)

    async def get_kasm_status(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/get_kasm_status", {"kasm_id": kasm_id, "user_id": user_id})

    async def destroy_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/destroy_kasm", {"kasm_id": kasm_id, "user_id": user_id})

    async def get_user_kasms(self, *, user_id: str) -> dict:
        return await self._json("POST", "/api/public/get_user_kasms", {"user_id": user_id})

    async def get_kasms(self) -> dict:
        return await self._json("POST", "/api/public/get_kasms")

    async def pause_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/pause_kasm", {"kasm_id": kasm_id, "user_id": user_id})

    async def resume_kasm(self, *, kasm_id: str, user_id: str) -> dict:
        return await self._json("POST", "/api/public/resume_kasm", {"kasm_id": kasm_id, "user_id": user_id})
