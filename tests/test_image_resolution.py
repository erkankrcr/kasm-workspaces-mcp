import pytest

from kasm_mcp.api.resolution import ImageResolutionError, resolve_image_id

IMAGES = [
    {"image_id": "abc123", "name": "kasmweb/chromium:1.19.0", "friendly_name": "Chromium (DMZ)", "description": "A free and open-source browser."},
    {"image_id": "def456", "name": "kasmweb/chromium:1.19.0", "friendly_name": "Chromium", "description": "A free and open-source browser."},
    {"image_id": "ghi789", "name": "kasmweb/kali-rolling:1.0", "friendly_name": "Kali Linux", "description": "Penetration testing distribution."},
]


def test_resolves_exact_image_id():
    assert resolve_image_id(IMAGES, "ghi789") == "ghi789"


def test_resolves_exact_friendly_name_case_insensitive():
    assert resolve_image_id(IMAGES, "kali linux") == "ghi789"


def test_resolves_unique_substring_match():
    assert resolve_image_id(IMAGES, "kali") == "ghi789"


def test_resolves_exact_friendly_name_over_substring_match_on_another_image():
    # "Chromium" is an exact friendly_name match; "Chromium (DMZ)" only a substring
    # match, so the exact one wins instead of being flagged ambiguous.
    assert resolve_image_id(IMAGES, "chromium") == "def456"


def test_raises_ambiguous_error_with_multiple_candidates():
    with pytest.raises(ImageResolutionError) as exc_info:
        resolve_image_id(IMAGES, "chrom")
    candidates = exc_info.value.candidates
    assert {c["image_id"] for c in candidates} == {"abc123", "def456"}


def test_raises_no_match_error_with_empty_candidates():
    with pytest.raises(ImageResolutionError) as exc_info:
        resolve_image_id(IMAGES, "nonexistent-workspace")
    assert exc_info.value.candidates == []
