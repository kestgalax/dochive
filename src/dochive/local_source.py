from __future__ import annotations

from collections import deque
from pathlib import Path
from urllib.request import url2pathname
from urllib.parse import unquote, urlparse

from .html_extract import extract_html_anchor_headings, file_uri, is_local_file_reference, parse_html_document
from .markdown_normalizer import normalize_markdown
from .models import MirrorConfig, MirrorIssue, MirrorRun, Page
from .url_utils import canonicalize_url


HTML_GLOBS = ("*.html", "*.htm", "*.xhtml")


def crawl_local_html(config: MirrorConfig) -> MirrorRun:
    source_path = Path(config.source).resolve()
    issues: list[MirrorIssue] = []
    if not source_path.exists():
        return MirrorRun(
            issues=[
                MirrorIssue(
                    kind="source_missing",
                    message="Local source path does not exist.",
                    path=str(source_path),
                    severity="error",
                )
            ]
        )
    if source_path.is_file():
        root_dir = source_path.parent
        start_files = [source_path]
    else:
        root_dir = source_path
        start_files = _find_start_files(root_dir)

    queue: deque[tuple[Path, int, str | None]] = deque((path, 0, None) for path in start_files)
    seen: set[Path] = set()
    pages: list[Page] = []

    while queue and len(pages) < config.max_pages:
        path, depth, parent_url = queue.popleft()
        path = path.resolve()
        if path in seen or depth > config.max_depth or not path.exists():
            continue
        seen.add(path)

        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            issues.append(
                MirrorIssue(
                    kind="local_read_failed",
                    message=str(exc),
                    path=str(path),
                    severity="error",
                )
            )
            continue
        page_url = canonicalize_url(file_uri(path))
        parser = parse_html_document(html, page_url)
        internal: list[str] = []
        external: list[str] = []

        for href, _text in parser.links:
            target = _local_target_path(href, root_dir, path.parent)
            if target and _is_html(target) and target.exists():
                target_url = canonicalize_url(file_uri(target))
                internal.append(target_url)
                if target.resolve() not in seen and depth + 1 <= config.max_depth:
                    queue.append((target, depth + 1, page_url))
            else:
                external.append(href)
                if target and _is_html(target) and not target.exists():
                    issues.append(
                        MirrorIssue(
                            kind="local_link_missing",
                            message="Linked local HTML file does not exist.",
                            path=str(target),
                            source=href,
                        )
                    )

        title = parser.title or path.stem.replace("-", " ").replace("_", " ").title()
        anchor_headings = extract_html_anchor_headings(html)
        pages.append(
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title=title,
                description=parser.description,
                markdown=normalize_markdown(
                    parser.markdown,
                    clean=config.clean_markdown,
                    extra_noise_lines=config.noise_lines,
                    anchor_headings=anchor_headings,
                ),
                depth=depth,
                parent_url=parent_url,
                links_internal=_unique(internal),
                links_external=_unique(external),
                anchor_headings=anchor_headings,
                assets=parser.assets,
                source_path=path,
            )
        )

    return MirrorRun(pages=pages, issues=issues)


def _find_start_files(root_dir: Path) -> list[Path]:
    for name in ("index.html", "index.htm"):
        candidate = root_dir / name
        if candidate.exists():
            return [candidate]
    files: list[Path] = []
    for pattern in HTML_GLOBS:
        files.extend(root_dir.glob(pattern))
    return sorted(files)[:1]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _local_target_path(href: str, root_dir: Path, base_dir: Path) -> Path | None:
    if not is_local_file_reference(href):
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return Path(url2pathname(unquote(parsed.path))).resolve()
    if parsed.path.startswith("/"):
        return (root_dir / parsed.path.lstrip("/")).resolve()
    return (base_dir / unquote(parsed.path)).resolve()


def _is_html(path: Path) -> bool:
    return path.suffix.lower() in {".html", ".htm", ".xhtml"}
