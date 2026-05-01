from __future__ import annotations

import re

from .models import Asset
from .url_utils import canonicalize_url, is_url


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff")
MARKDOWN_LINK_RE = re.compile(r"(!?\[([^\]]*)\]\()([^)]+)(\))")
NESTED_IMAGE_LINK_RE = re.compile(r"\[!\[[^\]]*\]\([^)]+\)\]\(([^)]+)\)")


def extract_markdown_assets(markdown: str, base_url: str) -> list[Asset]:
    assets: list[Asset] = []
    seen: set[tuple[str, str]] = set()
    for match in MARKDOWN_LINK_RE.finditer(markdown):
        prefix = match.group(1)
        alt = match.group(2).strip()
        target = match.group(3).strip()
        if target.startswith("#"):
            continue
        if not _is_image_target(target):
            continue
        source = canonicalize_url(target, base_url) if not is_url(target) else canonicalize_url(target)
        key = ("images", source)
        if key in seen:
            continue
        seen.add(key)
        assets.append(Asset(source=source, kind="images", alt=alt if prefix.startswith("![") else ""))
    for match in NESTED_IMAGE_LINK_RE.finditer(markdown):
        target = match.group(1).strip()
        if not _is_image_target(target):
            continue
        source = canonicalize_url(target, base_url) if not is_url(target) else canonicalize_url(target)
        key = ("images", source)
        if key in seen:
            continue
        seen.add(key)
        assets.append(Asset(source=source, kind="images"))
    return assets


def merge_assets(*groups: list[Asset]) -> list[Asset]:
    merged: list[Asset] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for asset in group:
            key = (asset.kind, asset.source)
            if key in seen:
                continue
            seen.add(key)
            merged.append(asset)
    return merged


def _is_image_target(target: str) -> bool:
    clean = target.split("#", 1)[0].split("?", 1)[0].lower()
    return clean.endswith(IMAGE_SUFFIXES)
