"""MCP tool registration for kasm-workspaces-mcp.

Tool *logic* lives in plain async functions (client, config, **kwargs) -> dict
so it's testable without going through the MCP protocol. ``build_server``
wires those functions into FastMCP-decorated closures.
"""

from __future__ import annotations

import asyncio
import base64
import sqlite3
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
from kasm_mcp.api.resolution import ImageResolutionError, resolve_image_id
from kasm_mcp.config import KasmConfig
from kasm_mcp.registry.db import connect as connect_registry_db
from kasm_mcp.registry.db import get_workspace_state, upsert_images, upsert_workspace_state
from kasm_mcp.security.validation import SecurityError, validate_command, validate_path

# ---------------------------------------------------------------------------
# Scoped-mode logic functions
# ---------------------------------------------------------------------------


async def create_kasm_session_logic(
    client: KasmAPIClient, config: KasmConfig, *, image: str, group_id: str, enable_sharing: bool = False
) -> dict:
    try:
        images_result = await client.get_images()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    try:
        image_id = resolve_image_id(images_result.get("images", []), image)
    except ImageResolutionError as e:
        return {"success": False, "error": str(e), "candidates": e.candidates}
    try:
        result = await client.request_kasm(
            image_id=image_id, user_id=config.user_id, group_id=group_id, enable_sharing=enable_sharing
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


async def connect_workspace_logic(
    client: KasmAPIClient,
    config: KasmConfig,
    conn: sqlite3.Connection,
    *,
    identifier: str,
    command: str | None = None,
    group_id: str | None = None,
    working_dir: str | None = None,
    user: str | None = None,
) -> dict:
    try:
        images_result = await client.get_images()
    except KasmAPIError as e:
        return {"success": False, "error": str(e)}
    images = images_result.get("images", [])
    upsert_images(conn, images)

    try:
        image_id = resolve_image_id(images, identifier)
    except ImageResolutionError as e:
        return {"success": False, "error": str(e), "candidates": e.candidates}

    state = get_workspace_state(conn, image_id)
    resolved_group_id = group_id or (state["last_group_id"] if state else None)
    if not resolved_group_id:
        return {
            "success": False,
            "error": f"No default group known yet for image {image_id!r}; pass group_id once to bootstrap it.",
            "error_type": "bootstrap_required",
        }

    kasm_id: str | None = None
    reused_session = False
    if state and state.get("last_kasm_id"):
        try:
            status_result = await client.get_kasm_status(kasm_id=state["last_kasm_id"], user_id=config.user_id)
            operational_status = status_result.get("kasm", status_result).get("operational_status")
        except KasmAPIError:
            operational_status = None
        if operational_status == "running":
            kasm_id = state["last_kasm_id"]
            reused_session = True

    if kasm_id is None:
        try:
            request_result = await client.request_kasm(
                image_id=image_id, user_id=config.user_id, group_id=resolved_group_id
            )
        except KasmAPIError as e:
            return {"success": False, "error": str(e)}
        kasm_id = request_result.get("kasm_id")
        if not kasm_id:
            return {"success": False, "error": "Kasm API returned no kasm_id from request_kasm."}

    upsert_workspace_state(conn, image_id=image_id, group_id=resolved_group_id, kasm_id=kasm_id)

    response: dict[str, Any] = {
        "success": True,
        "kasm_id": kasm_id,
        "image_id": image_id,
        "reused_session": reused_session,
    }
    if command is not None:
        response["command_result"] = await execute_kasm_command_logic(
            client, config, kasm_id=kasm_id, command=command, working_dir=working_dir, user=user
        )
    return response


_DIAGNOSTIC_FAKE_KASM_ID = "00000000-0000-0000-0000-000000000000"


async def _probe_permission(coro: Any) -> tuple[str, str | None]:
    """Run one lightweight, non-mutating API call and classify the result.

    Returns ("ok", None) on success, ("ok", detail) when the call failed for
    a reason unrelated to authorization (e.g. a fake id doesn't exist — that
    means the auth check itself passed), or ("missing", detail) when Kasm
    reported "Unauthorized".
    """
    try:
        await coro
        return "ok", None
    except KasmAPIError as e:
        message = str(e)
        if "unauthorized" in message.lower():
            return "missing", message
        return "ok", message


async def diagnose_permissions_logic(client: KasmAPIClient, config: KasmConfig) -> dict:
    """Probe which Kasm API-key permissions are present, without creating or
    modifying anything: real read-only calls for view-type permissions, and
    calls against a fake kasm_id (which Kasm rejects as "Invalid kasm_id"
    when authorized, or "Unauthorized" when not) for session-lifecycle
    permissions that would otherwise need a real session to test.
    """
    probes: dict[str, Any] = {
        "Images View": client.get_images(),
        "Sessions View": client.get_kasms(),
        "Users View": client.get_user(user_id=config.user_id),
        "User + Users Auth Session": client.get_kasm_status(kasm_id=_DIAGNOSTIC_FAKE_KASM_ID, user_id=config.user_id),
        "Sessions Modify": client.exec_command(kasm_id=_DIAGNOSTIC_FAKE_KASM_ID, user_id=config.user_id, command="true"),
    }
    checks: dict[str, dict[str, Any]] = {}
    for name, coro in probes.items():
        status, detail = await _probe_permission(coro)
        checks[name] = {"status": status, "detail": detail} if detail else {"status": status}

    missing = [name for name, result in checks.items() if result["status"] == "missing"]
    return {
        "success": True,
        "checks": checks,
        "missing_permissions": missing,
        "all_ok": not missing,
        "note": (
            "Fix: Kasm Admin -> Access Management -> API Keys (some versions: Settings -> Developers) "
            "-> this key -> Permissions tab -> grant the missing permission(s) above. "
            "A role label like 'Global Admin' shown elsewhere in the UI is not the same as this key's own "
            "Permissions tab. See docs/API_BEHAVIOR.md#required-api-key-permissions for the full breakdown."
        ),
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
    unofficial_client: KasmUnofficialAdminClient, *, name: str, friendly_name: str, **fields: Any
) -> dict:
    try:
        result = await unofficial_client.create_workspace_image(name=name, friendly_name=friendly_name, **fields)
    except (KasmAPIError, ValueError) as e:
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
    async def create_kasm_session(image: str, group_id: str, enable_sharing: bool = False) -> dict:
        """Create a new Kasm session.

        `image` may be an exact image_id, an exact friendly/docker name, or a
        unique substring (e.g. "kali" matches "Kali Linux") — resolved live
        against the current workspace image list, so newly added images work
        with no code changes. Set enable_sharing=True to get a usable share_id back.
        """
        return await create_kasm_session_logic(client, config, image=image, group_id=group_id, enable_sharing=enable_sharing)

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

    @mcp.tool()
    async def diagnose_permissions() -> dict:
        """Debug a misconfigured Kasm API key. Probes each permission this server
        needs (Images View, Sessions View, Users View, User + Users Auth Session,
        Sessions Modify) with safe, non-mutating calls — nothing is created or
        changed. Returns which permissions are missing and how to fix them.

        Use this first whenever a tool call fails with "Unauthorized" — it
        pinpoints exactly which permission box to check on the API key's own
        Permissions tab in the Kasm admin UI, instead of guessing.
        """
        return await diagnose_permissions_logic(client, config)

    if config.ssh_enabled:

        @mcp.tool()
        async def execute_kasm_command_ssh(
            kasm_id: str, command: str, working_dir: str | None = None, ssh_host: str | None = None
        ) -> dict:
            """⚠️ Backlog / Work In Progress — see docs/BACKLOG.md. Run a command
            via SSH and return real stdout/stderr/exit_code, instead of the
            Developer API's fire-and-forget exec.

            Only registered when KASM_SSH_ENABLED=true. Needs BOTH of these,
            confirmed independently required live (2026-09-11):
            - Network reachability from wherever this MCP server runs to the
              container's IP — same-LAN as the Kasm agent host is NOT enough;
              only reachable from inside the agent host itself, and only on
              the port KasmVNC listens on (6901 in the tested instance), not 22.
            - The workspace image must actually run an SSH daemon — stock
              kasmweb/* images (including a hand-registered Kali one) do not.
            This will very likely just fail unless you built a custom
            sshd-enabled image AND run this MCP server where it can reach the
            Kasm agent's Docker network.
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
        async def create_workspace_image(name: str, friendly_name: str, fields: dict[str, Any] | None = None) -> dict:
            """⚠️ Unofficial/undocumented Kasm API — may break on any Kasm upgrade. Requires KASM_UNOFFICIAL_API=true. Register a new workspace image.

            `name` is the docker image reference, e.g. "kasmweb/kali-rolling-desktop:1.18.0-rolling-daily".
            Pass additional Kasm image fields as a dict, e.g. {"docker_registry": "https://index.docker.io/v1/",
            "server_id": "...", "cores": 2.0, "memory_bytes": 2147483648, "description": "..."}. Do NOT pass
            "available", "categories", or "default_category" — confirmed live to crash Kasm's create_image
            with a 500 (see docs/ADMIN_UNOFFICIAL.md); set those afterward in the Kasm admin UI instead.
            """
            return await create_workspace_image_logic(
                unofficial_client, name=name, friendly_name=friendly_name, **(fields or {})
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

    if config.workspace_registry_enabled:
        registry_conn = connect_registry_db(config.db_path)

        @mcp.tool()
        async def connect_workspace(
            identifier: str, command: str | None = None, group_id: str | None = None, working_dir: str | None = None
        ) -> dict:
            """Requires KASM_ENABLE_WORKSPACE_REGISTRY=true. Find and connect to a Kasm
            workspace by name (e.g. "kali", "chromium") with no IDs required after the first use.

            Resolves `identifier` live against the current Kasm image list, reuses a
            still-running session for that image if one exists, otherwise creates one.
            The group_id used and the resulting kasm_id are remembered in a local SQLite
            registry, so after one bootstrap call with an explicit group_id, later calls
            for the same workspace need only `identifier`. Pass `command` to run it in the
            workspace immediately after connecting.
            """
            return await connect_workspace_logic(
                client, config, registry_conn, identifier=identifier, command=command,
                group_id=group_id, working_dir=working_dir,
            )

    return mcp
