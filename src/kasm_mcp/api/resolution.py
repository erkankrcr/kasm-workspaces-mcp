"""Resolve a user-supplied identifier (id, name, or fuzzy phrase) to a Kasm image_id.

Matches live against whatever ``get_images()`` currently returns, so a new
workspace image added in the Kasm admin panel is resolvable immediately —
no code change or lookup table needed here.
"""

from __future__ import annotations

from typing import Any


class ImageResolutionError(Exception):
    """Raised when an identifier matches zero or more than one image.

    ``candidates`` lists the ambiguous matches (empty when there were none),
    each as ``{"image_id": ..., "friendly_name": ...}``, so a caller can
    present options instead of guessing.
    """

    def __init__(self, message: str, candidates: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.candidates = candidates


def _candidate(image: dict[str, Any]) -> dict[str, Any]:
    return {"image_id": image.get("image_id"), "friendly_name": image.get("friendly_name")}


def resolve_image_id(images: list[dict[str, Any]], identifier: str) -> str:
    for image in images:
        if image.get("image_id") == identifier:
            return image["image_id"]

    needle = identifier.lower()

    exact = [
        image
        for image in images
        if needle in {str(image.get("friendly_name", "")).lower(), str(image.get("name", "")).lower()}
    ]
    if len(exact) == 1:
        return exact[0]["image_id"]
    if len(exact) > 1:
        raise ImageResolutionError(
            f"Ambiguous identifier {identifier!r}: matches {len(exact)} images.",
            [_candidate(image) for image in exact],
        )

    substring = [
        image
        for image in images
        if needle in str(image.get("friendly_name", "")).lower()
        or needle in str(image.get("description", "")).lower()
        or needle in str(image.get("name", "")).lower()
    ]
    if len(substring) == 1:
        return substring[0]["image_id"]
    if len(substring) > 1:
        raise ImageResolutionError(
            f"Ambiguous identifier {identifier!r}: matches {len(substring)} images.",
            [_candidate(image) for image in substring],
        )

    raise ImageResolutionError(f"No workspace image matches {identifier!r}.", [])
