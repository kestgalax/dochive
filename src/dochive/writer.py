from __future__ import annotations

import hashlib
import os
import re
import shutil
import ssl
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal embedded environments
    certifi = None

from .html_extract import is_local_file_reference
from .image_size import read_image_size
from .models import Asset, MirrorConfig, MirrorIssue, Page
from .url_utils import canonicalize_url, is_url, short_hash, source_root_name, url_to_markdown_relpath
from .yaml_writer import dumps_yaml

LINK_RE = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")
NESTED_IMAGE_LINK_RE = re.compile(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)")
IMAGE_TEXT_LINK_RE = re.compile(r"\[!\[[^\]]*\]\([^)]+\)([^\]]+)\]\(([^)]+)\)")
HTML_MEDIA_URL_RE = re.compile(
    r"(<(?:video|source)\b[^>]*\b(?:path|src)=[\"'])([^\"']+)([\"'][^>]*>)",
    re.IGNORECASE,
)
DOC_ROOT_FILENAME = ".doc-root.yaml"


def write_mirror(pages: list[Page], config: MirrorConfig, *, issues: list[MirrorIssue] | None = None) -> Path:
    root = config.out_dir / source_root_name(config.source)
    root.mkdir(parents=True, exist_ok=True)
    catalog_dir = root / "_catalog"
    catalog_dir.mkdir(exist_ok=True)
    previous_pages = _read_catalog_items(catalog_dir / "pages.yaml", "pages")
    previous_hashes = _catalog_hashes(previous_pages)

    child_urls_by_parent = _build_child_mapping(pages)
    path_by_url = _build_path_mapping(pages, config, child_urls_by_parent)
    sync_roots = _sync_roots(path_by_url.values())
    scoped_previous_hashes = {
        path: content_hash
        for path, content_hash in previous_hashes.items()
        if _path_in_roots(path, sync_roots)
    }
    _remove_stale_catalog_pages(root, scoped_previous_hashes.keys(), path_by_url.values())
    order_by_url = _build_order_mapping(pages)
    nav_parent_by_url = _nav_parent_by_url(pages)
    anchor_headings_by_url = {page.canonical_url: page.anchor_headings for page in pages}
    now = datetime.now(timezone.utc).isoformat()
    written_pages: list[dict[str, object]] = []
    written_links: list[dict[str, object]] = []
    written_assets: list[dict[str, object]] = []
    written_errors: list[dict[str, object]] = [issue.to_dict() for issue in issues or []]
    unresolved_internal_links: set[str] = set()

    for page in pages:
        relpath = path_by_url[page.canonical_url]
        output_path = root / Path(*relpath.parts)
        _remove_stale_page_alternates(root, relpath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        assets, asset_errors = _materialize_assets(page.assets, page, root, config, relpath)
        written_errors.extend(asset_errors)
        markdown = _rewrite_markdown_links(
            page,
            relpath,
            path_by_url,
            anchor_headings_by_url,
            assets,
            config,
        )
        content_hash = "sha256:" + hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        frontmatter = _page_frontmatter(
            page,
            relpath,
            path_by_url,
            child_urls_by_parent,
            order_by_url,
            nav_parent_by_url,
            assets,
            now,
            content_hash,
        )
        output_path.write_text("---\n" + dumps_yaml(frontmatter) + "---\n\n" + markdown, encoding="utf-8")

        written_pages.append(_page_catalog_entry(page, relpath, frontmatter))
        for target in page.links_internal:
            if target in path_by_url:
                written_links.append({"from": str(relpath), "to": str(path_by_url[target]), "kind": "internal"})
            else:
                unresolved_internal_links.add(target)
                written_links.append({"from": str(relpath), "to": target, "kind": "internal_unresolved"})
                written_errors.append(
                    {
                        "severity": "warning",
                        "kind": "internal_link_unresolved",
                        "message": "Internal link was discovered but not mirrored in this run.",
                        "url": target,
                        "path": str(relpath),
                        "source": page.source_url,
                    }
                )
        for target in page.links_external:
            written_links.append({"from": str(relpath), "to": target, "kind": "external"})
        for asset in assets:
            written_assets.append(
                {
                    "page": str(relpath),
                    "source": asset.source,
                    "kind": asset.kind,
                    "local_path": asset.local_path,
                    "width": asset.width,
                    "height": asset.height,
                }
            )

    merged_pages = _merge_catalog_items(previous_pages, written_pages, sync_roots, path_key="path")
    merged_links = _merge_catalog_items(
        _read_catalog_items(catalog_dir / "links.yaml", "links"),
        written_links,
        sync_roots,
        path_key="from",
    )
    merged_assets = _merge_catalog_items(
        _read_catalog_items(catalog_dir / "assets.yaml", "assets"),
        written_assets,
        sync_roots,
        path_key="page",
    )
    merged_errors = _merge_catalog_items(
        _read_catalog_items(catalog_dir / "errors.yaml", "errors"),
        written_errors,
        sync_roots,
        path_key="path",
    )
    _write_folder_indexes_from_catalog(root, merged_pages)
    _write_doc_root_files(root, [PurePosixPath(str(page["path"])) for page in merged_pages if page.get("path")])
    sync_report = _sync_report(scoped_previous_hashes, written_pages, source=config.source, generated_at=now)
    (catalog_dir / "pages.yaml").write_text(dumps_yaml({"pages": merged_pages}), encoding="utf-8")
    (catalog_dir / "links.yaml").write_text(dumps_yaml({"links": merged_links}), encoding="utf-8")
    (catalog_dir / "assets.yaml").write_text(dumps_yaml({"assets": merged_assets}), encoding="utf-8")
    (catalog_dir / "errors.yaml").write_text(dumps_yaml({"errors": merged_errors}), encoding="utf-8")
    (catalog_dir / "sync.yaml").write_text(dumps_yaml(sync_report), encoding="utf-8")
    _append_sync_history(catalog_dir / "sync_history.yaml", sync_report)
    (catalog_dir / "summary.yaml").write_text(
        dumps_yaml(
            _catalog_summary(
                root,
                merged_pages,
                merged_links,
                merged_assets,
                merged_errors,
                unresolved_internal_links,
                sync_report,
            )
        ),
        encoding="utf-8",
    )
    return root


def _read_previous_hashes(path: Path) -> dict[str, str]:
    return _catalog_hashes(_read_catalog_items(path, "pages"))


def _catalog_hashes(pages: list[dict[str, object]]) -> dict[str, str]:
    return {
        str(page["path"]): str(page["content_hash"])
        for page in pages
        if page.get("path") and page.get("content_hash")
    }


def _read_catalog_items(path: Path, root_key: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_root = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not in_root:
            in_root = line.strip() == f"{root_key}:"
            continue
        stripped = line.strip()
        if stripped == "-":
            if current:
                items.append(current)
            current = {}
            continue
        if not stripped or stripped in {"[]", "---"} or current is None or ": " not in stripped:
            continue
        key, value = stripped.split(": ", 1)
        current[key] = _yaml_scalar_value(value)
    if current:
        items.append(current)
    return items


def _yaml_scalar_value(value: str) -> object:
    value = value.strip()
    if value == "null":
        return None
    if value == "[]":
        return []
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return _yaml_string_value(value)


def _yaml_string_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _sync_report(
    previous_hashes: dict[str, str],
    pages: list[dict[str, object]],
    *,
    source: str,
    generated_at: str,
) -> dict[str, object]:
    current_hashes = {str(page["path"]): str(page["content_hash"]) for page in pages}
    previous_paths = set(previous_hashes)
    current_paths = set(current_hashes)
    added = sorted(current_paths - previous_paths)
    deleted = sorted(previous_paths - current_paths)
    changed = sorted(path for path in current_paths & previous_paths if current_hashes[path] != previous_hashes[path])
    unchanged = sorted(path for path in current_paths & previous_paths if current_hashes[path] == previous_hashes[path])
    return {
        "generated_at": generated_at,
        "source": source,
        "counts": {
            "added": len(added),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "deleted": len(deleted),
        },
        "added": added,
        "changed": changed,
        "unchanged": unchanged,
        "deleted": deleted,
    }


def _append_sync_history(path: Path, sync_report: dict[str, object]) -> None:
    document = "---\n" + dumps_yaml(sync_report)
    if path.exists() and path.stat().st_size > 0:
        with path.open("a", encoding="utf-8", newline="\n") as file:
            file.write("\n" + document)
        return
    path.write_text(document, encoding="utf-8")


def _catalog_summary(
    root: Path,
    pages: list[dict[str, object]],
    links: list[dict[str, object]],
    assets: list[dict[str, object]],
    errors: list[dict[str, object]],
    unresolved_internal_links: set[str],
    sync_report: dict[str, object],
) -> dict[str, object]:
    internal_links = [link for link in links if link.get("kind") == "internal"]
    unresolved_links = [link for link in links if link.get("kind") == "internal_unresolved"]
    external_links = [link for link in links if link.get("kind") == "external"]
    localized_assets = [asset for asset in assets if asset.get("local_path")]
    return {
        "root": str(root),
        "counts": {
            "pages": len(pages),
            "links_total": len(links),
            "links_internal": len(internal_links),
            "links_internal_unresolved": len(unresolved_links),
            "links_external": len(external_links),
            "assets_total": len(assets),
            "assets_localized": len(localized_assets),
            "errors": len([error for error in errors if error.get("severity") == "error"]),
            "warnings": len([error for error in errors if error.get("severity") != "error"]),
        },
        "unresolved_internal_links": sorted(unresolved_internal_links),
        "sync": sync_report["counts"],
    }


def _page_frontmatter(
    page: Page,
    relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    child_urls_by_parent: dict[str, list[str]],
    order_by_url: dict[str, int],
    nav_parent_by_url: dict[str, str | None],
    assets: list[Asset],
    crawled_at: str,
    content_hash: str,
) -> dict[str, object]:
    children = [str(path_by_url[url]) for url in child_urls_by_parent.get(page.canonical_url, []) if url in path_by_url]
    nav_parent_url = nav_parent_by_url.get(page.canonical_url)
    parent = str(path_by_url[nav_parent_url]) if nav_parent_url in path_by_url else None
    internal_links = [str(path_by_url[url]) for url in page.links_internal if url in path_by_url]
    return {
        "source_url": page.source_url,
        "canonical_url": page.canonical_url,
        "title": page.title,
        "description": page.description,
        "content_type": page.content_type,
        "status_code": page.status_code,
        "depth": page.depth,
        "path": str(relpath),
        "order": order_by_url.get(page.canonical_url, 0),
        "parent": parent,
        "children": children,
        "page_type": "doc",
        "tags": [],
        "summary": "",
        "content_hash": content_hash,
        "crawled_at": crawled_at,
        "assets": {
            "images": [asset.local_path for asset in assets if asset.kind == "images" and asset.local_path],
            "videos": [asset.local_path or asset.source for asset in assets if asset.kind in {"videos", "video"}],
            "files": [asset.local_path for asset in assets if asset.kind == "files" and asset.local_path],
        },
        "links": {
            "internal": internal_links,
            "external": page.links_external,
        },
    }


def _page_catalog_entry(page: Page, relpath: PurePosixPath, frontmatter: dict[str, object]) -> dict[str, object]:
    return {
        "path": str(relpath),
        "title": page.title,
        "source_url": page.source_url,
        "depth": page.depth,
        "order": frontmatter["order"],
        "summary": frontmatter["summary"],
        "tags": frontmatter["tags"],
        "content_hash": frontmatter["content_hash"],
    }


def _build_path_mapping(
    pages: list[Page],
    config: MirrorConfig,
    child_urls_by_parent: dict[str, list[str]],
) -> dict[str, PurePosixPath]:
    if is_url(config.source):
        mapping = {page.canonical_url: url_to_markdown_relpath(page.canonical_url) for page in pages}
        return _apply_gramax_layout(pages, mapping, child_urls_by_parent)

    source_path = Path(config.source).resolve()
    root_dir = source_path.parent if source_path.is_file() else source_path
    mapping: dict[str, PurePosixPath] = {}
    for page in pages:
        if not page.source_path:
            mapping[page.canonical_url] = url_to_markdown_relpath(page.canonical_url)
            continue
        try:
            rel = page.source_path.resolve().relative_to(root_dir)
        except ValueError:
            rel = Path(page.source_path.name)
        mapping[page.canonical_url] = _local_html_relpath(rel)
    return _apply_gramax_layout(pages, mapping, child_urls_by_parent)


def _apply_gramax_layout(
    pages: list[Page],
    mapping: dict[str, PurePosixPath],
    child_urls_by_parent: dict[str, list[str]],
) -> dict[str, PurePosixPath]:
    final_mapping = dict(mapping)
    parents_with_children = set(child_urls_by_parent)
    nav_url_by_path = _nav_url_by_path(pages)

    for parent_url in parents_with_children:
        if parent_url in final_mapping:
            final_mapping[parent_url] = _page_index_path(final_mapping[parent_url])

    for page in pages:
        nav_parent_url = _nav_parent_url(page, final_mapping.keys(), nav_url_by_path)
        if nav_parent_url not in parents_with_children or nav_parent_url not in final_mapping:
            continue
        current = final_mapping[page.canonical_url]
        parent_dir = final_mapping[nav_parent_url].parent
        if _is_relative_to(current, parent_dir):
            continue
        final_mapping[page.canonical_url] = _move_page_under_folder(current, parent_dir)

    return final_mapping


def _page_index_path(path: PurePosixPath) -> PurePosixPath:
    if path.name == "_index.md":
        return path
    if path.suffix.lower() == ".md":
        if path.parent.name.lower() == path.stem.lower():
            return path.parent / "_index.md"
        return path.parent / path.stem / "_index.md"
    return path / "_index.md"


def _move_page_under_folder(path: PurePosixPath, folder: PurePosixPath) -> PurePosixPath:
    if path.name == "_index.md":
        return folder / path.parent.name / "_index.md"
    return folder / path.name


def _is_relative_to(path: PurePosixPath, parent: PurePosixPath) -> bool:
    if path == parent:
        return True
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _build_child_mapping(pages: list[Page]) -> dict[str, list[str]]:
    existing = {page.canonical_url for page in pages}
    nav_url_by_path = _nav_url_by_path(pages)
    children: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        nav_parent_url = _nav_parent_url(page, existing, nav_url_by_path)
        if nav_parent_url in existing:
            children[nav_parent_url].append(page.canonical_url)
    return {parent: list(dict.fromkeys(urls)) for parent, urls in children.items()}


def _build_order_mapping(pages: list[Page]) -> dict[str, int]:
    existing = {page.canonical_url for page in pages}
    nav_url_by_path = _nav_url_by_path(pages)
    sibling_groups: dict[str | None, list[str]] = defaultdict(list)
    for page in pages:
        parent = _nav_parent_url(page, existing, nav_url_by_path)
        sibling_groups[parent].append(page.canonical_url)
    return {
        url: index
        for urls in sibling_groups.values()
        for index, url in enumerate(dict.fromkeys(urls), start=1)
    }


def _remove_stale_page_alternates(root: Path, relpath: PurePosixPath) -> None:
    if relpath.name == "_index.md":
        stale = root / Path(*relpath.parent.parts) if str(relpath.parent) != "." else root
        stale = stale.with_suffix(".md")
        _unlink_file(stale)
        return
    if relpath.suffix.lower() == ".md":
        stale = root / Path(*relpath.parent.parts, relpath.stem, "_index.md")
        _unlink_file(stale)
        _remove_empty_parents(stale.parent, root)


def _remove_stale_catalog_pages(root: Path, previous_paths: object, current_paths: object) -> None:
    current = {str(path) for path in current_paths}
    root_resolved = root.resolve()
    for previous in previous_paths:
        if not isinstance(previous, str) or previous in current:
            continue
        relpath = PurePosixPath(previous)
        if relpath.suffix.lower() != ".md":
            continue
        stale = root / Path(*relpath.parts)
        try:
            stale_resolved = stale.resolve()
        except OSError:
            continue
        if stale_resolved != root_resolved and root_resolved not in stale_resolved.parents:
            continue
        _unlink_file(stale)
        _remove_empty_parents(stale.parent, root)


def _merge_catalog_items(
    previous: list[dict[str, object]],
    current: list[dict[str, object]],
    sync_roots: tuple[PurePosixPath, ...],
    *,
    path_key: str,
) -> list[dict[str, object]]:
    preserved = [
        item
        for item in previous
        if not _path_in_roots(str(item.get(path_key) or ""), sync_roots)
    ]
    return [*preserved, *current]


def _sync_roots(paths: object) -> tuple[PurePosixPath, ...]:
    roots: set[PurePosixPath] = set()
    for path in paths:
        if not isinstance(path, PurePosixPath):
            continue
        parts = path.parts
        for index, part in enumerate(parts[:-1]):
            if part.lower() == "content" and index + 1 < len(parts):
                roots.add(PurePosixPath(*parts[: index + 2]))
                break
        else:
            roots.add(PurePosixPath(parts[0]) if parts else PurePosixPath("."))
    return tuple(sorted(roots, key=str))


def _path_in_roots(path: str, roots: tuple[PurePosixPath, ...]) -> bool:
    if not path:
        return False
    relpath = PurePosixPath(path)
    return any(_is_relative_to(relpath, root) for root in roots)


def _unlink_file(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        return


def _remove_empty_parents(path: Path, stop_at: Path) -> None:
    stop_at = stop_at.resolve()
    current = path
    while True:
        try:
            resolved = current.resolve()
        except OSError:
            return
        if resolved == stop_at or stop_at not in resolved.parents:
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _nav_parent_by_url(pages: list[Page]) -> dict[str, str | None]:
    existing = {page.canonical_url for page in pages}
    nav_url_by_path = _nav_url_by_path(pages)
    return {
        page.canonical_url: _nav_parent_url(page, existing, nav_url_by_path)
        for page in pages
    }


def _nav_url_by_path(pages: list[Page]) -> dict[tuple[str, ...], str]:
    mapping: dict[tuple[str, ...], str] = {}
    for page in pages:
        if page.nav_path:
            mapping.setdefault(page.nav_path, page.canonical_url)
    return mapping


def _nav_parent_url(
    page: Page,
    existing_urls: object,
    nav_url_by_path: dict[tuple[str, ...], str],
) -> str | None:
    existing = set(existing_urls)
    if page.nav_parent_url == page.canonical_url:
        return None
    if page.nav_parent_url in existing:
        return page.nav_parent_url
    if len(page.nav_path) > 1:
        parent_url = nav_url_by_path.get(page.nav_path[:-1])
        return parent_url if parent_url != page.canonical_url else None
    return None


def _local_html_relpath(path: Path) -> PurePosixPath:
    parts = list(path.parts)
    filename = Path(parts[-1])
    if filename.name.lower() in {"index.html", "index.htm", "index.xhtml"}:
        parts[-1] = "index.md"
    elif filename.suffix.lower() in {".html", ".htm", ".xhtml"}:
        parts[-1] = filename.with_suffix(".md").name
    else:
        parts.append("index.md")
    return PurePosixPath(*parts)


def _write_folder_indexes(
    root: Path,
    pages: list[Page],
    path_by_url: dict[str, PurePosixPath],
    order_by_url: dict[str, int],
) -> None:
    folders: dict[PurePosixPath, list[Page]] = defaultdict(list)
    for page in pages:
        folders[path_by_url[page.canonical_url].parent].append(page)

    all_folders = set(folders)
    for folder in list(all_folders):
        current = folder
        while str(current) != ".":
            current = current.parent
            all_folders.add(current)

    for folder in sorted(all_folders, key=lambda item: str(item)):
        folder_path = root if str(folder) == "." else root / Path(*folder.parts)
        folder_path.mkdir(parents=True, exist_ok=True)
        child_dirs = sorted(
            str(candidate.relative_to(folder))
            for candidate in all_folders
            if candidate != folder and candidate.parent == folder
        )
        folder_pages = sorted(
            folders.get(folder, []),
            key=lambda page: (order_by_url.get(page.canonical_url, 0), str(path_by_url[page.canonical_url])),
        )
        payload = {
            "path": "" if str(folder) == "." else str(folder),
            "title": _folder_title(folder),
            "summary": "",
            "children": [{"path": child, "title": _folder_title(PurePosixPath(child))} for child in child_dirs],
            "pages": [
                {
                    "file": path_by_url[page.canonical_url].name,
                    "path": str(path_by_url[page.canonical_url]),
                    "title": page.title,
                    "source_url": page.source_url,
                    "order": order_by_url.get(page.canonical_url, 0),
                    "tags": [],
                }
                for page in folder_pages
            ],
            "keywords": sorted({word for page in folder_pages for word in _keywords(page.title)}),
        }
        (folder_path / "_index.yaml").write_text(dumps_yaml(payload), encoding="utf-8")


def _write_folder_indexes_from_catalog(root: Path, pages: list[dict[str, object]]) -> None:
    folders: dict[PurePosixPath, list[dict[str, object]]] = defaultdict(list)
    for page in pages:
        path = page.get("path")
        if not isinstance(path, str):
            continue
        relpath = PurePosixPath(path)
        folders[relpath.parent].append(page)

    all_folders = set(folders)
    for folder in list(all_folders):
        current = folder
        while str(current) != ".":
            current = current.parent
            all_folders.add(current)

    for folder in sorted(all_folders, key=lambda item: str(item)):
        folder_path = root if str(folder) == "." else root / Path(*folder.parts)
        folder_path.mkdir(parents=True, exist_ok=True)
        child_dirs = sorted(
            str(candidate.relative_to(folder))
            for candidate in all_folders
            if candidate != folder and candidate.parent == folder
        )
        folder_pages = sorted(
            folders.get(folder, []),
            key=lambda page: (int(page.get("order") or 0), str(page.get("path") or "")),
        )
        payload = {
            "path": "" if str(folder) == "." else str(folder),
            "title": _folder_title(folder),
            "summary": "",
            "children": [{"path": child, "title": _folder_title(PurePosixPath(child))} for child in child_dirs],
            "pages": [
                {
                    "file": PurePosixPath(str(page["path"])).name,
                    "path": str(page["path"]),
                    "title": page.get("title", ""),
                    "source_url": page.get("source_url", ""),
                    "order": page.get("order", 0),
                    "tags": page.get("tags", []),
                }
                for page in folder_pages
                if page.get("path")
            ],
            "keywords": sorted({word for page in folder_pages for word in _keywords(str(page.get("title") or ""))}),
        }
        (folder_path / "_index.yaml").write_text(dumps_yaml(payload), encoding="utf-8")


def _write_doc_root_files(root: Path, paths: object) -> None:
    for doc_root in _doc_root_folders(paths):
        folder_path = root if str(doc_root) == "." else root / Path(*doc_root.parts)
        folder_path.mkdir(parents=True, exist_ok=True)
        doc_root_path = folder_path / DOC_ROOT_FILENAME
        if not doc_root_path.exists():
            doc_root_path.write_text(_doc_root_content(folder_path.name or "docs"), encoding="utf-8")


def _doc_root_folders(paths: object) -> list[PurePosixPath]:
    folders: set[PurePosixPath] = set()
    for path in paths:
        if not isinstance(path, PurePosixPath):
            continue
        parts = path.parts
        for index, part in enumerate(parts):
            if part.lower() == "content":
                folders.add(PurePosixPath(*parts[:index]) if index else PurePosixPath("."))
                break
    return sorted(folders, key=lambda folder: str(folder))


def _doc_root_content(title: str) -> str:
    return f"title: {title}\nsyntax: XML\nsupportedLanguages: []\nproperties: []\n"


def _folder_title(folder: PurePosixPath) -> str:
    name = folder.name if str(folder) != "." else "Documentation Mirror"
    return name.replace("-", " ").replace("_", " ").title()


def _keywords(title: str) -> list[str]:
    return [word.lower() for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", title)]


def _rewrite_markdown_links(
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
    assets: list[Asset],
    config: MirrorConfig,
) -> str:
    markdown = page.markdown
    asset_by_source = {asset.source: asset for asset in assets if asset.local_path}
    markdown = IMAGE_TEXT_LINK_RE.sub(lambda match: f"[{match.group(1).strip()}]({match.group(2).strip()})", markdown)

    if config.image_link_mode == "plain":
        markdown = NESTED_IMAGE_LINK_RE.sub(
            lambda match: _nested_image_to_plain(match, page, current_relpath, asset_by_source, config),
            markdown,
        )
    else:
        markdown = NESTED_IMAGE_LINK_RE.sub(
            lambda match: _nested_image_to_linked(
                match,
                page,
                current_relpath,
                path_by_url,
                anchor_headings_by_url,
                asset_by_source,
            ),
            markdown,
        )

    def replace(match: re.Match[str]) -> str:
        if config.image_render_mode == "html" and match.group(1).startswith("!["):
            asset = _asset_for_target(match.group(2).strip(), page, asset_by_source)
            if asset:
                return _render_image(
                    _relative_asset_path(asset, current_relpath),
                    _image_alt_from_prefix(match.group(1)),
                    asset,
                    config,
                )
        return _rewrite_single_target(
            match,
            page,
            current_relpath,
            path_by_url,
            anchor_headings_by_url,
            asset_by_source,
        )

    markdown = LINK_RE.sub(replace, markdown)
    markdown = _rewrite_html_media_sources(
        markdown,
        page,
        current_relpath,
        path_by_url,
        anchor_headings_by_url,
        asset_by_source,
    )
    markdown = _normalize_media_spacing(markdown)
    return _render_details_sections(markdown)


def _normalize_media_spacing(markdown: str) -> str:
    output: list[str] = []
    lines = markdown.splitlines()
    in_fence = False
    for index, line in enumerate(lines):
        if _is_fenced_code_line(line):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence and _is_media_line(line):
            if output and output[-1].strip():
                output.append("")
            output.append(line.strip())
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if next_line.strip():
                output.append("")
            continue
        output.append(line)
    return "\n".join(output)


def _is_fenced_code_line(line: str) -> bool:
    return bool(re.match(r"^\s*(```|~~~)", line))


def _is_media_line(line: str) -> bool:
    stripped = line.strip().lower()
    return stripped.startswith(("<image ", "<video "))


def _render_details_sections(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    details_open = False

    for line in lines:
        summary = _details_summary_text(line)
        if summary:
            if details_open:
                output.append("")
                output.append("</details>")
                output.append("")
            elif output and output[-1].strip():
                output.append("")
            output.append("<details>")
            output.append("")
            output.append(f"<summary>{summary}</summary>")
            output.append("")
            details_open = True
            continue

        if details_open and _details_boundary_line(line):
            output.append("")
            output.append("</details>")
            output.append("")
            details_open = False

        if details_open:
            line = _normalize_details_line(line)
        output.append(line)

    if details_open:
        output.append("")
        output.append("</details>")

    return "\n".join(output) + ("\n" if markdown.endswith("\n") else "")


def _details_summary_text(line: str) -> str | None:
    match = re.fullmatch(r"\[(Подробное описание|Подробнее)\]\([^)]+\)", line.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def _details_boundary_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    leading_spaces = len(line) - len(line.lstrip(" "))
    return bool(
        re.match(r"#{1,6}\s+\S", stripped)
        or (leading_spaces <= 2 and re.match(r"[*-]\s+\S", stripped))
    )


def _normalize_details_line(line: str) -> str:
    if match := re.fullmatch(r"\s*\*\*(.+?)\*\*\s*", line):
        return f"##### {match.group(1).strip()}"
    return re.sub(r"^ {4,}([*-]\s+\S)", r"  \1", line)


def _rewrite_html_media_sources(
    markdown: str,
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
    asset_by_source: dict[str, Asset],
) -> str:
    def replace(match: re.Match[str]) -> str:
        rewritten = _rewrite_target_text(
            match.group(2).strip(),
            page,
            current_relpath,
            path_by_url,
            anchor_headings_by_url,
            asset_by_source,
        )
        return match.group(1) + rewritten + match.group(3)

    return HTML_MEDIA_URL_RE.sub(replace, markdown)


def _nested_image_to_plain(
    match: re.Match[str],
    page: Page,
    current_relpath: PurePosixPath,
    asset_by_source: dict[str, Asset],
    config: MirrorConfig,
) -> str:
    alt, thumb_target, full_target = (group.strip() for group in match.groups())
    full_asset = _asset_for_target(full_target, page, asset_by_source)
    thumb_asset = _asset_for_target(thumb_target, page, asset_by_source)
    asset = full_asset or thumb_asset
    if not asset:
        return f"![{alt}]({full_target})"
    return _render_image(_relative_asset_path(asset, current_relpath), alt, asset, config)


def _image_alt_from_prefix(prefix: str) -> str:
    match = re.match(r"!\[([^\]]*)\]\(", prefix)
    return match.group(1) if match else ""


def _render_image(path: str, alt: str, asset: Asset, config: MirrorConfig) -> str:
    if config.image_render_mode == "html":
        return f'\n\n<image src="{path}"{_image_size_attrs(asset, config)} float="center"/>\n\n'
    return f"![{alt}]({path})"


def _image_size_attrs(asset: Asset, config: MirrorConfig) -> str:
    if config.image_size_mode == "none" or not asset.width or not asset.height:
        return ""

    original_width = asset.width
    width = asset.width
    height = asset.height
    scale = 100
    if config.image_size_mode == "max-width" and config.image_max_width and width > config.image_max_width:
        ratio = config.image_max_width / width
        width = config.image_max_width
        height = max(1, round(height * ratio))
        scale = max(1, round((width / original_width) * 100))

    return f' crop="0,0,100,100" scale="{scale}" width="{width}px" height="{height}px"'


def _nested_image_to_linked(
    match: re.Match[str],
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
    asset_by_source: dict[str, Asset],
) -> str:
    alt, thumb_target, full_target = (group.strip() for group in match.groups())
    thumb = _rewrite_target_text(thumb_target, page, current_relpath, path_by_url, anchor_headings_by_url, asset_by_source)
    full = _rewrite_target_text(full_target, page, current_relpath, path_by_url, anchor_headings_by_url, asset_by_source)
    return f"[![{alt}]({thumb})]({full})"


def _asset_for_target(target: str, page: Page, asset_by_source: dict[str, Asset]) -> Asset | None:
    if target in asset_by_source:
        return asset_by_source[target]
    normalized = _normalize_markdown_target(target, page)
    return asset_by_source.get(normalized)


def _rewrite_single_target(
    match: re.Match[str],
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
    asset_by_source: dict[str, Asset],
) -> str:
    prefix, target, suffix = match.groups()
    clean_target = target.strip()
    if clean_target in asset_by_source:
        return prefix + _relative_asset_path(asset_by_source[clean_target], current_relpath) + suffix
    if not clean_target.startswith("#"):
        normalized = _normalize_markdown_target(clean_target, page)
        if normalized in asset_by_source:
            return prefix + _relative_asset_path(asset_by_source[normalized], current_relpath) + suffix
    rewritten = _rewrite_page_target(clean_target, page, current_relpath, path_by_url, anchor_headings_by_url)
    if rewritten is not None:
        return prefix + rewritten + suffix
    return match.group(0)


def _rewrite_target_text(
    target: str,
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
    asset_by_source: dict[str, Asset],
) -> str:
    if target in asset_by_source:
        return _relative_asset_path(asset_by_source[target], current_relpath)
    if not target.startswith("#"):
        normalized = _normalize_markdown_target(target, page)
        if normalized in asset_by_source:
            return _relative_asset_path(asset_by_source[normalized], current_relpath)
    rewritten = _rewrite_page_target(target, page, current_relpath, path_by_url, anchor_headings_by_url)
    if rewritten is not None:
        return rewritten
    return target


def _rewrite_page_target(
    target: str,
    page: Page,
    current_relpath: PurePosixPath,
    path_by_url: dict[str, PurePosixPath],
    anchor_headings_by_url: dict[str, dict[str, str]],
) -> str | None:
    base_url, fragment = _normalize_target_base_and_fragment(target, page)
    if base_url not in path_by_url:
        return None

    rel = _relative_page_path(path_by_url[base_url], current_relpath)
    anchor = _gramax_anchor(fragment, base_url, anchor_headings_by_url)
    if not anchor:
        return rel
    if path_by_url[base_url] == current_relpath:
        return f"#{anchor}"
    return f"{rel}#{anchor}"


def _relative_page_path(target_relpath: PurePosixPath, current_relpath: PurePosixPath) -> str:
    return os.path.relpath(
        Path(*target_relpath.parts),
        start=Path(*current_relpath.parent.parts) if str(current_relpath.parent) != "." else Path("."),
    ).replace("\\", "/")


def _gramax_anchor(
    fragment: str | None,
    base_url: str,
    anchor_headings_by_url: dict[str, dict[str, str]],
) -> str:
    if not fragment:
        return ""
    clean = unquote(fragment).strip()
    if not clean:
        return ""
    return anchor_headings_by_url.get(base_url, {}).get(clean, clean)


def _normalize_target_base_and_fragment(target: str, page: Page) -> tuple[str, str | None]:
    parsed = urlparse(target)
    fragment = parsed.fragment or None
    if target.startswith("#"):
        return page.canonical_url, target[1:]
    if fragment:
        target = target.split("#", 1)[0]
    if not target:
        return page.canonical_url, fragment
    return _normalize_markdown_target(target, page), fragment


def _relative_asset_path(asset: Asset, current_relpath: PurePosixPath) -> str:
    asset_path = PurePosixPath(asset.local_path or "")
    rel = os.path.relpath(
        Path(*asset_path.parts),
        start=Path(*current_relpath.parent.parts) if str(current_relpath.parent) != "." else Path("."),
    ).replace("\\", "/")
    if not rel.startswith((".", "/")):
        return "./" + rel
    return rel


def _normalize_markdown_target(target: str, page: Page) -> str:
    if is_url(target):
        return target.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    if page.source_path and is_local_file_reference(target):
        parsed = urlparse(target)
        if parsed.scheme == "file":
            local = Path(url2pathname(unquote(parsed.path))).resolve()
        else:
            local = (page.source_path.parent / unquote(parsed.path)).resolve()
        return local.as_uri().rstrip("/")
    if is_url(page.canonical_url):
        return canonicalize_url(target, page.canonical_url)
    return target


def _materialize_assets(
    assets: list[Asset],
    page: Page,
    root: Path,
    config: MirrorConfig,
    page_relpath: PurePosixPath,
) -> tuple[list[Asset], list[dict[str, object]]]:
    materialized: list[Asset] = []
    errors: list[dict[str, object]] = []
    for asset in assets:
        if not config.save_asset_kinds or asset.kind not in config.save_asset_kinds:
            materialized.append(asset)
            continue
        target_rel = _asset_relpath(asset, page_relpath)
        target = root / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if page.source_path and is_local_file_reference(asset.source):
                src_path = _asset_local_path(asset.source, page.source_path.parent)
                if src_path.exists() and src_path.is_file():
                    shutil.copy2(src_path, target)
                    materialized.append(_asset_with_local_metadata(asset, target_rel.as_posix(), target))
                    continue
                errors.append(
                    {
                        "severity": "warning",
                        "kind": "asset_missing",
                        "message": "Asset file does not exist.",
                        "url": page.source_url,
                        "path": str(page_relpath),
                        "source": asset.source,
                    }
                )
                materialized.append(asset)
                continue
            elif is_url(asset.source):
                _download_url(asset.source, target)
                materialized.append(_asset_with_local_metadata(asset, target_rel.as_posix(), target))
                continue
        except OSError as exc:
            errors.append(
                {
                    "severity": "warning",
                    "kind": "asset_localize_failed",
                    "message": str(exc),
                    "url": page.source_url,
                    "path": str(page_relpath),
                    "source": asset.source,
                }
            )
        materialized.append(asset)
    return materialized, errors


def _download_url(source: str, target: Path) -> None:
    context = None
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(source, context=context) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)


def _asset_with_local_metadata(asset: Asset, local_path: str, file_path: Path) -> Asset:
    width = asset.width
    height = asset.height
    if asset.kind == "images":
        size = read_image_size(file_path)
        if size:
            width, height = size
    return Asset(asset.source, asset.kind, asset.alt, local_path, width, height)


def _asset_relpath(asset: Asset, page_relpath: PurePosixPath) -> Path:
    parsed = urlparse(asset.source)
    name = Path(unquote(parsed.path)).name or f"{short_hash(asset.source)}.bin"
    stem = Path(name).stem or short_hash(asset.source)
    suffix = Path(name).suffix or ".bin"
    page_asset_dir = Path(*page_relpath.parent.parts)
    if page_relpath.name != "_index.md":
        page_asset_dir = page_asset_dir / page_relpath.stem
    return page_asset_dir / f"{stem}-{short_hash(asset.source)}{suffix}"


def _asset_local_path(source: str, base_dir: Path) -> Path:
    parsed = urlparse(source)
    if parsed.scheme == "file":
        return Path(url2pathname(unquote(parsed.path))).resolve()
    return (base_dir / unquote(parsed.path)).resolve()
