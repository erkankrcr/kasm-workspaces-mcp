"""Low-level authenticated HTTP calls to the Kasm Developer API.

Shared by api/client.py (``/api/public/*``) and admin_unofficial/client.py
(``/api/admin/*`` — same api_key auth, per Kasm's own "Using Undocumented
APIs" support guidance).
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urljoin

import aiohttp


class KasmAPIError(Exception):
    """Raised for any non-successful Kasm API response."""


def _error_message(status: int, body: Mapping[str, Any]) -> str:
    return str(body.get("error_message") or body.get("error") or f"HTTP {status}")


async def request_json(
    session: aiohttp.ClientSession,
    api_url: str,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    data: Mapping[str, Any] | None = None,
) -> dict:
    """POST/GET a Kasm endpoint expecting a JSON body back.

    Raises KasmAPIError both for HTTP >=400 responses and for HTTP 200
    responses that carry an ``error_message``/``error`` field — Kasm does
    both depending on the failure (observed live: "No resources are
    available..." comes back as a 200 with error_message).
    """
    body = {"api_key": api_key, "api_key_secret": api_secret, **(data or {})}
    url = urljoin(api_url.rstrip("/") + "/", path.lstrip("/"))
    async with session.request(method, url, json=body) as resp:
        payload = await resp.json()
        if resp.status >= 400 or "error_message" in payload or "error" in payload:
            raise KasmAPIError(_error_message(resp.status, payload))
        return payload


async def request_binary(
    session: aiohttp.ClientSession,
    api_url: str,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    data: Mapping[str, Any] | None = None,
) -> bytes:
    """POST a Kasm endpoint expecting a raw binary body back (e.g. a JPEG screenshot)."""
    body = {"api_key": api_key, "api_key_secret": api_secret, **(data or {})}
    url = urljoin(api_url.rstrip("/") + "/", path.lstrip("/"))
    async with session.request(method, url, json=body) as resp:
        content_type = resp.headers.get("content-type", "")
        if resp.status >= 400 or "application/json" in content_type:
            payload = await resp.json()
            raise KasmAPIError(_error_message(resp.status, payload))
        return await resp.read()
