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
        self, *, image_id: str, user_id: str, group_id: str, enable_sharing: bool = False
    ) -> dict:
        data: dict[str, Any] = {"image_id": image_id, "user_id": user_id, "group_id": group_id}
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

    async def get_kasm_screenshot(
        self, *, kasm_id: str, user_id: str, width: int | None = None, height: int | None = None
    ) -> bytes:
        data: dict[str, Any] = {"kasm_id": kasm_id, "user_id": user_id}
        if width:
            data["width"] = width
        if height:
            data["height"] = height
        return await self._binary("POST", "/api/public/get_kasm_screenshot", data)

    async def exec_command(
        self,
        *,
        kasm_id: str,
        user_id: str,
        command: str,
        working_dir: str | None = None,
        user: str | None = None,
    ) -> None:
        """Fire-and-forget: the real Kasm API never returns stdout/exit_code
        for this call, so this method's return is always ``None`` on success;
        it only raises ``KasmAPIError`` if the *dispatch itself* failed."""
        exec_config: dict[str, Any] = {"cmd": command}
        if working_dir:
            exec_config["workdir"] = working_dir
        if user:
            exec_config["user"] = user
        await self._json(
            "POST",
            "/api/public/exec_command_kasm",
            {"kasm_id": kasm_id, "user_id": user_id, "exec_config": exec_config},
        )

    async def join_kasm(self, *, share_id: str, user_id: str | None = None) -> dict:
        data: dict[str, Any] = {"share_id": share_id}
        if user_id:
            data["user_id"] = user_id
        return await self._json("POST", "/api/public/join_kasm", data)

    async def get_images(self) -> dict:
        return await self._json("POST", "/api/public/get_images")

    # -- Official admin endpoints (require an API key with User/Group management
    # permissions; only wired into server.py when KASM_ADMIN_MODE=true) --

    async def create_user(
        self, *, username: str, password: str, first_name: str = "", last_name: str = "", group_id: str | None = None
    ) -> dict:
        target_user: dict[str, Any] = {"username": username, "password": password, "first_name": first_name, "last_name": last_name}
        data: dict[str, Any] = {"target_user": target_user}
        if group_id:
            data["group_id"] = group_id
        return await self._json("POST", "/api/public/create_user", data)

    async def update_user(self, *, user_id: str, **fields: Any) -> dict:
        target_user = {"user_id": user_id, **fields}
        return await self._json("POST", "/api/public/update_user", {"target_user": target_user})

    async def delete_user(self, *, user_id: str, force: bool = False) -> dict:
        return await self._json("POST", "/api/public/delete_user", {"target_user": {"user_id": user_id}, "force": force})

    async def get_user(self, *, user_id: str | None = None, username: str | None = None) -> dict:
        target_user: dict[str, Any] = {}
        if user_id:
            target_user["user_id"] = user_id
        if username:
            target_user["username"] = username
        return await self._json("POST", "/api/public/get_user", {"target_user": target_user})

    async def get_users(self) -> dict:
        return await self._json("POST", "/api/public/get_users")

    async def logout_user(self, *, user_id: str) -> dict:
        return await self._json("POST", "/api/public/logout_user", {"target_user": {"user_id": user_id}})

    async def add_user_to_group(self, *, user_id: str, group_id: str) -> dict:
        return await self._json("POST", "/api/public/add_user_group", {"target_user": {"user_id": user_id}, "target_group": {"group_id": group_id}})

    async def remove_user_from_group(self, *, user_id: str, group_id: str) -> dict:
        return await self._json("POST", "/api/public/remove_user_group", {"target_user": {"user_id": user_id}, "target_group": {"group_id": group_id}})
