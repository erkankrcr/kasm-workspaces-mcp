"""Entrypoint: ``python -m kasm_mcp`` / the ``kasm-mcp`` console script."""

from __future__ import annotations

from kasm_mcp.api.client import KasmAPIClient
from kasm_mcp.config import load_config
from kasm_mcp.server import build_server


def main() -> None:
    config = load_config()
    client = KasmAPIClient(config.api_url, config.api_key, config.api_secret)
    server = build_server(client, config)
    server.run()


if __name__ == "__main__":
    main()
