"""MCP tool registration for kasm-workspaces-mcp.

Tool *logic* lives in plain async functions (client, config, **kwargs) -> dict
so it's testable without going through the MCP protocol. ``build_server``
wires those functions into FastMCP-decorated closures.
"""

from __future__ import annotations

import base64

# The installed mcp SDK is 2.x, where FastMCP was renamed to MCPServer and
# moved to mcp.server.mcpserver (mcp.server.fastmcp no longer exists there).
# Alias it back to FastMCP so the rest of this module reads the same as
# it would against the mcp 1.x API the task brief was written against.
from mcp.server.mcpserver import MCPServer as FastMCP

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.api.http import KasmAPIError
from kasm_mcp.config import KasmConfig
from kasm_mcp.security.validation import SecurityError, validate_command

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
    try:
        image_bytes = await client.get_kasm_screenshot(kasm_id=kasm_id, user_id=config.user_id, width=width, height=height)
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    if save_to_file:
        with open(save_to_file, "wb") as f:
            f.write(image_bytes)
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


async def get_available_workspaces_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    try:
        result = await client.get_images()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "images": result.get("images", [])}


# ---------------------------------------------------------------------------
# FastMCP wiring
# ---------------------------------------------------------------------------


def build_server(client: KasmAPIClient, config: KasmConfig) -> FastMCP:
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

    return mcp
