"""MCP tool registration for kasm-workspaces-mcp.

Tool *logic* lives in plain async functions (client, config, **kwargs) -> dict
so it's testable without going through the MCP protocol. ``build_server``
wires those functions into FastMCP-decorated closures.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

# The installed mcp SDK is 2.x, where FastMCP was renamed to MCPServer and
# moved to mcp.server.mcpserver (mcp.server.fastmcp no longer exists there).
# Alias it back to FastMCP so the rest of this module reads the same as
# it would against the mcp 1.x API the task brief was written against.
from mcp.server.mcpserver import MCPServer as FastMCP

from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient
from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.security.validation import SecurityError, validate_command, validate_path

# ---------------------------------------------------------------------------
# Scoped-mode logic functions
# ---------------------------------------------------------------------------


async def create_kasm_session_logic(
    client: KasmAPIClient, config: KasmConfig, *, image_name: str, group_id: str, enable_sharing: bool = False
) -> dict:
    try:
        result = await client.request_kasm(
            image_name=image_name, user_id=config.user_id, group_id=group_id, enable_sharing=enable_sharing
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "kasm_id": result.get("kasm_id"),
        "session_url": result.get("kasm_url"),
        "share_id": result.get("share_id"),
        "status": result.get("status", "created"),
    }


async def destroy_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.destroy_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def pause_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.pause_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def resume_kasm_session_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        await client.resume_kasm(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id}


async def get_session_status_logic(client: KasmAPIClient, config: KasmConfig, *, kasm_id: str) -> dict:
    try:
        result = await client.get_kasm_status(kasm_id=kasm_id, user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "kasm_id": kasm_id, "status": result.get("kasm", result)}


async def list_user_sessions_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_user_kasms(user_id=config.user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "sessions": result.get("kasms", [])}


async def get_share_link_logic(client: KasmAPIClient, config: KasmConfig, *, share_id: str) -> dict:
    try:
        result = await client.join_kasm(share_id=share_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "share_url": result.get("kasm_url"),
        "note": "View-only link unless the Kasm group's shared_session_full_control setting is enabled.",
    }


async def get_session_screenshot_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    width: int | None = None,
    height: int | None = None,
    save_to_file: str | None = None,
) -> dict:
    if save_to_file:
        try:
            validate_path(save_to_file, config.allowed_roots, "screenshot save")
        except SecurityError as e:
            return {"success": False, "error": str(e), "error_type": "security"}
    try:
        image_bytes = await client.get_kasm_screenshot(kasm_id=kasm_id, user_id=config.user_id, width=width, height=height)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    if save_to_file:
        await asyncio.to_thread(Path(save_to_file).write_bytes, image_bytes)
        return {"success": True, "kasm_id": kasm_id, "file_path": save_to_file}
    return {"success": True, "kasm_id": kasm_id, "screenshot_base64": base64.b64encode(image_bytes).decode()}


async def execute_kasm_command_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    command: str,
    working_dir: str | None = None,
    user: str | None = None,
) -> dict:
    try:
        validate_command(command)
    except SecurityError as e:
        return {"success": False, "error": str(e), "error_type": "security"}
    try:
        await client.exec_command(
            kasm_id=kasm_id, user_id=config.user_id, command=command, working_dir=working_dir, user=user
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {
        "success": True,
        "dispatched": True,
        "note": "Kasm's exec API never returns command output or exit code; this only confirms dispatch.",
    }


async def execute_kasm_command_ssh_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    *,
    kasm_id: str,
    command: str,
    working_dir: str | None = None,
    ssh_host: str | None = None,
) -> dict:
    from kasm_mcp.ssh.exec_backend import SSHNotConfiguredError, resolve_ssh_host, ssh_exec

    try:
        validate_command(command)
    except SecurityError as e:
        return {"success": False, "error": str(e), "error_type": "security"}

    if not config.ssh_enabled or not config.ssh_key_path:
        return {
            "success": False,
            "error": "SSH exec is not configured (set KASM_SSH_ENABLED=true and KASM_SSH_KEY_PATH).",
            "error_type": "not_configured",
        }

    container_ip: str | None = None
    try:
        status = await client.get_kasm_status(kasm_id=kasm_id, user_id=config.user_id)
        container_ip = status.get("kasm", status).get("container_ip")
    except KasmAPIError:
        pass  # host resolution can still succeed via explicit param/override

    try:
        host = resolve_ssh_host(explicit_host=ssh_host, override=config.ssh_host_override, container_ip=container_ip)
    except SSHNotConfiguredError as e:
        return {"success": False, "error": str(e), "error_type": "not_configured"}

    try:
        result = await ssh_exec(
            host=host, port=22, username=config.ssh_user, key_path=config.ssh_key_path,
            command=command, working_dir=working_dir,
        )
    except Exception as e:  # noqa: BLE001 - surface any transport/auth failure to the caller
        return {"success": False, "error": f"SSH exec failed: {e}"}

    return {"success": True, **result}


async def get_available_workspaces_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_images()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "images": result.get("images", [])}


# ---------------------------------------------------------------------------
# Admin-mode logic functions
# ---------------------------------------------------------------------------

_ADMIN_WARNING = "⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments."


async def create_kasm_user_logic(
    client: KasmAPIClient, config: KasmConfig, *, username: str, password: str,
    first_name: str = "", last_name: str = "", group_id: str | None = None,
) -> dict:
    try:
        result = await client.create_user(
            username=username, password=password, first_name=first_name, last_name=last_name, group_id=group_id
        )
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def update_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, **fields: Any) -> dict:
    try:
        result = await client.update_user(user_id=user_id, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def delete_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, force: bool = False) -> dict:
    try:
        await client.delete_user(user_id=user_id, force=force)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id}


async def get_kasm_user_logic(
    client: KasmAPIClient, config: KasmConfig, *, user_id: str | None = None, username: str | None = None
) -> dict:
    try:
        result = await client.get_user(user_id=user_id, username=username)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user": result.get("user")}


async def get_kasm_users_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_users()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "users": result.get("users", [])}


async def logout_kasm_user_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str) -> dict:
    try:
        await client.logout_user(user_id=user_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id}


async def add_user_to_group_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, group_id: str) -> dict:
    try:
        await client.add_user_to_group(user_id=user_id, group_id=group_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id, "group_id": group_id}


async def remove_user_from_group_logic(client: KasmAPIClient, config: KasmConfig, *, user_id: str, group_id: str) -> dict:
    try:
        await client.remove_user_from_group(user_id=user_id, group_id=group_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "user_id": user_id, "group_id": group_id}


# ---------------------------------------------------------------------------
# Unofficial admin-panel logic functions
# ---------------------------------------------------------------------------

_UNOFFICIAL_WARNING = "⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true."


async def get_registries_logic(unofficial_client: KasmUnofficialAdminClient) -> dict:
    try:
        result = await unofficial_client.get_registries()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registries": result.get("registries", [])}


async def create_registry_logic(
    unofficial_client: KasmUnofficialAdminClient, *, url: str, username: str | None = None, password: str | None = None
) -> dict:
    try:
        result = await unofficial_client.create_registry(url=url, username=username, password=password)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registry": result.get("registry")}


async def delete_registry_logic(unofficial_client: KasmUnofficialAdminClient, *, registry_id: str) -> dict:
    try:
        await unofficial_client.delete_registry(registry_id=registry_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "registry_id": registry_id}


async def create_workspace_image_logic(
    unofficial_client: KasmUnofficialAdminClient, *, image_name: str, friendly_name: str, **fields: Any
) -> dict:
    try:
        result = await unofficial_client.create_workspace_image(image_name=image_name, friendly_name=friendly_name, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image": result.get("image")}


async def update_workspace_image_logic(unofficial_client: KasmUnofficialAdminClient, *, image_id: str, **fields: Any) -> dict:
    try:
        result = await unofficial_client.update_workspace_image(image_id=image_id, **fields)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image": result.get("image")}


async def delete_workspace_image_logic(unofficial_client: KasmUnofficialAdminClient, *, image_id: str) -> dict:
    try:
        await unofficial_client.delete_workspace_image(image_id=image_id)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "image_id": image_id}


# ---------------------------------------------------------------------------
# FastMCP wiring
# ---------------------------------------------------------------------------


def build_server(
    client: KasmAPIClient, config: KasmConfig, unofficial_client: KasmUnofficialAdminClient | None = None
) -> FastMCP:
    mcp = FastMCP("kasm-workspaces-mcp")

    @mcp.tool()
    async def create_kasm_session(image_name: str, group_id: str, enable_sharing: bool = False) -> dict:
        """Create a new Kasm session. Set enable_sharing=True to get a usable share_id back."""
        return await create_kasm_session_logic(client, config, image_name=image_name, group_id=group_id, enable_sharing=enable_sharing)

    @mcp.tool()
    async def destroy_kasm_session(kasm_id: str) -> dict:
        """Permanently destroy a Kasm session."""
        return await destroy_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def pause_kasm_session(kasm_id: str) -> dict:
        """Pause a Kasm session."""
        return await pause_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def resume_kasm_session(kasm_id: str) -> dict:
        """Resume a paused Kasm session."""
        return await resume_kasm_session_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def get_session_status(kasm_id: str) -> dict:
        """Get the current status of a Kasm session."""
        return await get_session_status_logic(client, config, kasm_id=kasm_id)

    @mcp.tool()
    async def list_user_sessions() -> dict:
        """List active sessions for the configured user."""
        return await list_user_sessions_logic(client, config)

    @mcp.tool()
    async def get_share_link(share_id: str) -> dict:
        """Get a view-only share link for a session created with enable_sharing=True."""
        return await get_share_link_logic(client, config, share_id=share_id)

    @mcp.tool()
    async def get_session_screenshot(
        kasm_id: str, width: int | None = None, height: int | None = None, save_to_file: str | None = None
    ) -> dict:
        """Capture a screenshot of a session. Pass save_to_file to write a JPEG; otherwise returns base64."""
        return await get_session_screenshot_logic(
            client, config, kasm_id=kasm_id, width=width, height=height, save_to_file=save_to_file
        )

    @mcp.tool()
    async def execute_kasm_command(
        kasm_id: str, command: str, working_dir: str | None = None, user: str | None = None
    ) -> dict:
        """Dispatch a command inside a session. Kasm's API never returns output/exit_code for this call."""
        return await execute_kasm_command_logic(
            client, config, kasm_id=kasm_id, command=command, working_dir=working_dir, user=user
        )

    @mcp.tool()
    async def get_available_workspaces() -> dict:
        """List available workspace images."""
        return await get_available_workspaces_logic(client, config)

    if config.ssh_enabled:

        @mcp.tool()
        async def execute_kasm_command_ssh(
            kasm_id: str, command: str, working_dir: str | None = None, ssh_host: str | None = None
        ) -> dict:
            """Run a command via SSH and return real stdout/stderr/exit_code.

            Only registered when KASM_SSH_ENABLED=true. Requires the MCP
            server to have network access to the session's host.
            """
            return await execute_kasm_command_ssh_logic(
                client, config, kasm_id=kasm_id, command=command, working_dir=working_dir, ssh_host=ssh_host
            )

    if config.admin_mode:

        @mcp.tool()
        async def create_kasm_user(
            username: str, password: str, first_name: str = "", last_name: str = "", group_id: str | None = None
        ) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Create a new Kasm user."""
            return await create_kasm_user_logic(
                client, config, username=username, password=password,
                first_name=first_name, last_name=last_name, group_id=group_id,
            )

        @mcp.tool()
        async def update_kasm_user(user_id: str, fields: dict[str, Any] | None = None) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Update fields on an existing Kasm user.

            Pass Kasm user fields to update as a dict, e.g. {"first_name": "Bob", "last_name": "Smith", "locked": False}.
            """
            return await update_kasm_user_logic(client, config, user_id=user_id, **(fields or {}))

        @mcp.tool()
        async def delete_kasm_user(user_id: str, force: bool = False) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Delete a Kasm user."""
            return await delete_kasm_user_logic(client, config, user_id=user_id, force=force)

        @mcp.tool()
        async def get_kasm_user(user_id: str | None = None, username: str | None = None) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Look up a Kasm user by id or username."""
            return await get_kasm_user_logic(client, config, user_id=user_id, username=username)

        @mcp.tool()
        async def get_kasm_users() -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. List all Kasm users."""
            return await get_kasm_users_logic(client, config)

        @mcp.tool()
        async def logout_kasm_user(user_id: str) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Force-logout a Kasm user's active sessions."""
            return await logout_kasm_user_logic(client, config, user_id=user_id)

        @mcp.tool()
        async def add_user_to_group(user_id: str, group_id: str) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Add a user to a Kasm group."""
            return await add_user_to_group_logic(client, config, user_id=user_id, group_id=group_id)

        @mcp.tool()
        async def remove_user_from_group(user_id: str, group_id: str) -> dict:
            """⚠️ Admin-privileged action — requires an API key with User Management permissions. Not recommended for shared or production Kasm deployments. Remove a user from a Kasm group."""
            return await remove_user_from_group_logic(client, config, user_id=user_id, group_id=group_id)

    if config.unofficial_api:
        unofficial_client = unofficial_client or KasmUnofficialAdminClient(config.api_url, config.api_key, config.api_secret)

        @mcp.tool()
        async def get_registries() -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. List configured Docker registries."""
            return await get_registries_logic(unofficial_client)

        @mcp.tool()
        async def create_registry(url: str, username: str | None = None, password: str | None = None) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Register a Docker registry."""
            return await create_registry_logic(unofficial_client, url=url, username=username, password=password)

        @mcp.tool()
        async def delete_registry(registry_id: str) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Delete a configured Docker registry."""
            return await delete_registry_logic(unofficial_client, registry_id=registry_id)

        @mcp.tool()
        async def create_workspace_image(image_name: str, friendly_name: str, fields: dict[str, Any] | None = None) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Register a new workspace image.

            Pass additional Kasm image fields as a dict, e.g. {"docker_image": "kasmweb/chrome:1.16.0", "cores": 2, "memory": 2147483648}.
            """
            return await create_workspace_image_logic(
                unofficial_client, image_name=image_name, friendly_name=friendly_name, **(fields or {})
            )

        @mcp.tool()
        async def update_workspace_image(image_id: str, fields: dict[str, Any] | None = None) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Update an existing workspace image's fields.

            Pass Kasm image fields to update as a dict, e.g. {"friendly_name": "Chrome (Updated)", "cores": 4}.
            """
            return await update_workspace_image_logic(unofficial_client, image_id=image_id, **(fields or {}))

        @mcp.tool()
        async def delete_workspace_image(image_id: str) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Delete a workspace image."""
            return await delete_workspace_image_logic(unofficial_client, image_id=image_id)

    return mcp
