"""Entrypoint: ``python -m kasm_mcp`` / the ``kasm-mcp`` console script."""

from __future__ import annotations

import asyncio

from dotenv import find_dotenv, load_dotenv

from kasm_mcp.admin_unofficial.client import KasmUnofficialAdminClient
from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.config import load_config
from kasm_mcp.server import build_server


async def _run() -> None:
    config = load_config()
    client = KasmAPIClient(config.api_url, config.api_key, config.api_secret)
    unofficial_client = (
        KasmUnofficialAdminClient(config.api_url, config.api_key, config.api_secret)
        if config.unofficial_api
        else None
    )
    server = build_server(client, config, unofficial_client)
    try:
        # server.run() is a synchronous wrapper that does anyio.run(self.run_stdio_async);
        # calling run_stdio_async directly here keeps the client sessions (created lazily
        # on first request, inside this same event loop) closeable in that same loop.
        await server.run_stdio_async()
    finally:
        await client.close()
        if unofficial_client is not None:
            await unofficial_client.close()


def main() -> None:
    # Loads a .env file from the current working directory (or a parent of
    # it) into os.environ, without overriding variables already set there
    # (e.g. by an MCP client's own "env" config). find_dotenv(usecwd=True)
    # is required: the plain default search walks up from this installed
    # file's location (inside the venv) rather than from where the command
    # was invoked.
    load_dotenv(find_dotenv(usecwd=True))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
