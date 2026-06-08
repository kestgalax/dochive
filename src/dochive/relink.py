from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .models import MirrorConfig, Page
from .writer import (
    LINK_RE,
    _append_sync_history,
    _catalog_hashes,
    _catalog_summary,
    _read_catalog_items,
    _rewrite_markdown_links,
    _sync_report,
)
from .yaml_writer import dumps_yaml, loads_yaml


@dataclass(frozen=True)
class RelinkResult:
    changed: int = 0
    unchanged: int = 0
    skipped: int = 0
    changed_paths: list[str] = field(default_factory=list)


def build_link_path_map(
    structure_items: list[dict[str, object]],
    pages_items: list[dict[str, object]],
) -> dict[str, PurePosixPath]:
    mapping: dict[str, PurePosixPath] = {}
    for item in structure_items:
        canonical_url = item.get("canonical_url")
        path = item.get("path")
        if isinstance(canonical_url, str) and canonical_url and isinstance(path, str) and path:
            mapping[canonical_url] = PurePosixPath(path)
    for item in pages_items:
        if item.get("placeholder") is True:
            continue
        canonical_url = item.get("canonical_url")
        path = item.get("path")
        if isinstance(canonical_url, str) and canonical_url and isinstance(path, str) and path:
            mapping[canonical_url] = PurePosixPath(path)
    return mapping


def relink_mirror(
    root: Path,
    *,
    dry_run: bool = False,
    path_prefix: str | None = None,
) -> RelinkResult:
    catalog_dir = root / "_catalog"
    if not catalog_dir.is_dir():
        raise FileNotFoundError(f"Missing catalog directory: {catalog_dir}")

    _write_progress("Reading catalog...")
    structure_items = _read_catalog_items(catalog_dir / "structure.yaml", "structure")
    pages_items = _read_catalog_items(catalog_dir / "pages.yaml", "pages")
    if not pages_items:
        raise ValueError(f"No pages found in {catalog_dir / 'pages.yaml'}")

    link_path_by_url = build_link_path_map(structure_items, pages_items)
    previous_hashes = _catalog_hashes(pages_items)
    config = MirrorConfig(source=_mirror_source_url(pages_items), out_dir=root.parent)
    prefix = PurePosixPath(path_prefix.strip("/")) if path_prefix else None

    candidates = [
        item
        for item in pages_items
        if item.get("placeholder") is not True and isinstance(item.get("path"), str) and item.get("path")
    ]
    _write_progress(f"Relinking {len(candidates)} pages...")

    changed_paths: list[str] = []
    unchanged = 0
    skipped = 0
    updated_pages = [dict(item) for item in pages_items]
    pages_by_path = {str(item.get("path")): item for item in updated_pages if item.get("path")}
    all_links: list[dict[str, object]] = []
    processed_from: set[str] = set()

    for item in candidates:
        relpath = PurePosixPath(str(item["path"]))
        if prefix and not _path_has_prefix(relpath, prefix):
            skipped += 1
            continue

        page_path = root / Path(*relpath.parts)
        if not page_path.is_file():
            _write_progress(f"warning: missing page file, skipping: {relpath}")
            skipped += 1
            continue
        processed_from.add(str(relpath))

        frontmatter_text, body = _split_markdown_document(page_path.read_text(encoding="utf-8"))
        if not frontmatter_text:
            skipped += 1
            continue

        frontmatter = loads_yaml(frontmatter_text)
        page = _page_from_frontmatter(frontmatter, body)
        rewritten = _rewrite_markdown_links(
            page,
            relpath,
            link_path_by_url,
            {},
            [],
            config,
        )

        if rewritten == body:
            unchanged += 1
            all_links.extend(_link_catalog_entries(relpath, body, page, link_path_by_url))
            continue

        changed_paths.append(str(relpath))
        internal_links, external_links = _frontmatter_links_from_markdown(rewritten)
        content_hash = "sha256:" + hashlib.sha256(rewritten.encode("utf-8")).hexdigest()

        if not dry_run:
            frontmatter["links"] = {"internal": internal_links, "external": external_links}
            frontmatter["content_hash"] = content_hash
            page_path.write_text(
                "---\n" + dumps_yaml(frontmatter) + "---\n\n" + rewritten,
                encoding="utf-8",
            )
            catalog_entry = pages_by_path.get(str(relpath))
            if catalog_entry is not None:
                catalog_entry["content_hash"] = content_hash

        all_links.extend(_link_catalog_entries(relpath, rewritten, page, link_path_by_url))

    if prefix:
        existing_links = _read_catalog_items(catalog_dir / "links.yaml", "links")
        all_links = [
            *[link for link in existing_links if str(link.get("from") or "") not in processed_from],
            *all_links,
        ]

    changed = len(changed_paths)
    if dry_run:
        return RelinkResult(changed=changed, unchanged=unchanged, skipped=skipped, changed_paths=changed_paths)

    _write_progress("Updating catalog...")
    now = datetime.now(timezone.utc).isoformat()
    sync_report = _sync_report(previous_hashes, updated_pages, source=config.source, generated_at=now)
    assets_items = _read_catalog_items(catalog_dir / "assets.yaml", "assets")
    errors_items = _read_catalog_items(catalog_dir / "errors.yaml", "errors")

    (catalog_dir / "pages.yaml").write_text(dumps_yaml({"pages": updated_pages}), encoding="utf-8")
    (catalog_dir / "links.yaml").write_text(dumps_yaml({"links": all_links}), encoding="utf-8")
    (catalog_dir / "sync.yaml").write_text(dumps_yaml(sync_report), encoding="utf-8")
    _append_sync_history(catalog_dir / "sync_history.yaml", sync_report)
    (catalog_dir / "errors.yaml").write_text(dumps_yaml({"errors": errors_items}), encoding="utf-8")
    (catalog_dir / "summary.yaml").write_text(
        dumps_yaml(
            _catalog_summary(
                root,
                updated_pages,
                all_links,
                assets_items,
                errors_items,
                set(),
                sync_report,
            )
        ),
        encoding="utf-8",
    )
    return RelinkResult(changed=changed, unchanged=unchanged, skipped=skipped, changed_paths=changed_paths)


def _mirror_source_url(pages_items: list[dict[str, object]]) -> str:
    for item in pages_items:
        canonical_url = item.get("canonical_url")
        if isinstance(canonical_url, str) and canonical_url.startswith("http"):
            return canonical_url
    return "https://localhost/"


def _path_has_prefix(relpath: PurePosixPath, prefix: PurePosixPath) -> bool:
    if str(prefix) == ".":
        return True
    return relpath == prefix or str(relpath).startswith(f"{prefix}/")


def _split_markdown_document(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip() + "\n", parts[2].lstrip("\n")


def _page_from_frontmatter(frontmatter: dict[str, object], body: str) -> Page:
    canonical_url = str(frontmatter.get("canonical_url") or "")
    source_url = str(frontmatter.get("source_url") or canonical_url)
    title = str(frontmatter.get("title") or "")
    description = str(frontmatter.get("description") or "")
    depth = int(frontmatter.get("depth") or 0)
    nav_path_value = frontmatter.get("nav_path")
    nav_path = tuple(str(part) for part in nav_path_value) if isinstance(nav_path_value, list) else ()
    nav_parent_url = frontmatter.get("nav_parent_url")
    return Page(
        source_url=source_url,
        canonical_url=canonical_url,
        title=title,
        description=description,
        markdown=body,
        depth=depth,
        nav_path=nav_path,
        nav_parent_url=str(nav_parent_url) if isinstance(nav_parent_url, str) else None,
    )


def _extract_markdown_link_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for match in LINK_RE.finditer(markdown):
        if match.group(1).startswith("!"):
            continue
        targets.append(match.group(2).strip())
    return targets


def _frontmatter_links_from_markdown(markdown: str) -> tuple[list[str], list[str]]:
    internal: list[str] = []
    external: list[str] = []
    seen: set[str] = set()
    for target in _extract_markdown_link_targets(markdown):
        if target in seen or target.startswith("#"):
            continue
        seen.add(target)
        if target.startswith("http://") or target.startswith("https://"):
            external.append(target)
        else:
            internal.append(target)
    return internal, external


def _link_catalog_entries(
    relpath: PurePosixPath,
    markdown: str,
    page: Page,
    link_path_by_url: dict[str, PurePosixPath],
) -> list[dict[str, object]]:
    from .writer import _normalize_target_base_and_fragment

    entries: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for target in _extract_markdown_link_targets(markdown):
        if target.startswith("#"):
            continue
        base_url, _ = _normalize_target_base_and_fragment(target, page)
        if target.startswith("http://") or target.startswith("https://"):
            if base_url in link_path_by_url:
                kind = "internal"
                to_value = str(link_path_by_url[base_url])
            else:
                kind = "external"
                to_value = target
        else:
            kind = "internal"
            to_value = target
        key = (str(relpath), kind, to_value)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"from": str(relpath), "to": to_value, "kind": kind})
    return entries


def _write_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
