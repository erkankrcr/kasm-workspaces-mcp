"""Local SQLite-backed cache of Kasm workspace images and per-image session state.

Refreshed on every ``connect_workspace`` call (see ``server.py``) so a newly
added Kasm image is picked up automatically, and remembers the last
group_id/kasm_id used per image so repeat calls need no IDs supplied.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images_cache (
            image_id TEXT PRIMARY KEY,
            name TEXT,
            friendly_name TEXT,
            description TEXT,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_state (
            image_id TEXT PRIMARY KEY,
            last_group_id TEXT NOT NULL,
            last_kasm_id TEXT NOT NULL,
            last_used_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_images(conn: sqlite3.Connection, images: list[dict[str, Any]]) -> None:
    now = _now()
    conn.executemany(
        """
        INSERT INTO images_cache (image_id, name, friendly_name, description, last_seen_at)
        VALUES (:image_id, :name, :friendly_name, :description, :last_seen_at)
        ON CONFLICT(image_id) DO UPDATE SET
            name = excluded.name,
            friendly_name = excluded.friendly_name,
            description = excluded.description,
            last_seen_at = excluded.last_seen_at
        """,
        [
            {
                "image_id": image.get("image_id"),
                "name": image.get("name"),
                "friendly_name": image.get("friendly_name"),
                "description": image.get("description"),
                "last_seen_at": now,
            }
            for image in images
        ],
    )
    conn.commit()


def get_cached_images(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT image_id, name, friendly_name, description FROM images_cache").fetchall()
    return [dict(row) for row in rows]


def get_workspace_state(conn: sqlite3.Connection, image_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT image_id, last_group_id, last_kasm_id FROM workspace_state WHERE image_id = ?",
        (image_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def upsert_workspace_state(conn: sqlite3.Connection, *, image_id: str, group_id: str, kasm_id: str) -> None:
    conn.execute(
        """
        INSERT INTO workspace_state (image_id, last_group_id, last_kasm_id, last_used_at)
        VALUES (:image_id, :group_id, :kasm_id, :last_used_at)
        ON CONFLICT(image_id) DO UPDATE SET
            last_group_id = excluded.last_group_id,
            last_kasm_id = excluded.last_kasm_id,
            last_used_at = excluded.last_used_at
        """,
        {"image_id": image_id, "group_id": group_id, "kasm_id": kasm_id, "last_used_at": _now()},
    )
    conn.commit()
