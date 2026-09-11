from kasm_mcp.registry.db import (
    connect,
    get_cached_images,
    get_workspace_state,
    upsert_images,
    upsert_workspace_state,
)


def test_connect_creates_parent_directories(tmp_path):
    db_path = tmp_path / "nested" / "registry.db"
    conn = connect(str(db_path))
    try:
        assert db_path.exists()
    finally:
        conn.close()


def test_upsert_images_then_get_cached_images_roundtrip(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    upsert_images(conn, [
        {"image_id": "abc", "name": "kasmweb/kali-rolling:1.0", "friendly_name": "Kali Linux", "description": "Pentest distro."},
    ])
    cached = get_cached_images(conn)
    assert cached == [
        {"image_id": "abc", "name": "kasmweb/kali-rolling:1.0", "friendly_name": "Kali Linux", "description": "Pentest distro."},
    ]


def test_upsert_images_overwrites_existing_row_for_same_image_id(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    upsert_images(conn, [{"image_id": "abc", "name": "old", "friendly_name": "Old Name", "description": "old"}])
    upsert_images(conn, [{"image_id": "abc", "name": "new", "friendly_name": "New Name", "description": "new"}])
    cached = get_cached_images(conn)
    assert len(cached) == 1
    assert cached[0]["friendly_name"] == "New Name"


def test_get_workspace_state_returns_none_when_absent(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    assert get_workspace_state(conn, "abc") is None


def test_upsert_workspace_state_then_get_roundtrip(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    upsert_workspace_state(conn, image_id="abc", group_id="grp1", kasm_id="kasm1")
    state = get_workspace_state(conn, "abc")
    assert state == {"image_id": "abc", "last_group_id": "grp1", "last_kasm_id": "kasm1"}


def test_upsert_workspace_state_overwrites_existing_row(tmp_path):
    conn = connect(str(tmp_path / "registry.db"))
    upsert_workspace_state(conn, image_id="abc", group_id="grp1", kasm_id="kasm1")
    upsert_workspace_state(conn, image_id="abc", group_id="grp2", kasm_id="kasm2")
    state = get_workspace_state(conn, "abc")
    assert state == {"image_id": "abc", "last_group_id": "grp2", "last_kasm_id": "kasm2"}
