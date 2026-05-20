from __future__ import annotations

import hashlib
import re
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse, urlunparse


HTML_SUFFIXES = {".html", ".htm", ".xhtml"}


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def canonicalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", url)
    parsed = urlparse(absolute)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = quote(unquote(parsed.path or "/"), safe="/:@")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def canonicalize_with_language_prefix(url: str, root_url: str) -> str:
    canonical = canonicalize_url(url)
    root = urlparse(canonicalize_url(root_url))
    parsed = urlparse(canonical)
    if parsed.netloc.lower() != root.netloc.lower():
        return canonical

    root_parts = [part for part in root.path.split("/") if part]
    if not root_parts or len(root_parts[0]) != 2:
        return canonical

    target_parts = [part for part in parsed.path.split("/") if part]
    if not target_parts or target_parts[0].lower() == root_parts[0].lower():
        return canonical

    root_tail = "/".join(root_parts[1:])
    target_tail = "/".join(target_parts)
    if root_tail and not (target_tail == root_tail or target_tail.startswith(root_tail + "/")):
        return canonical

    normalized_path = "/" + "/".join([root_parts[0], *target_parts])
    return parsed._replace(path=normalized_path, params="", query="", fragment="").geturl()


def extract_tocpath(url: str, base_url: str | None = None) -> tuple[str, ...]:
    absolute = urljoin(base_url or "", url)
    parsed = urlparse(absolute)
    query = parse_qs(parsed.query, keep_blank_values=False)
    values = next((value for key, value in query.items() if key.lower() == "tocpath"), [])
    if not values:
        return ()
    parts = []
    for part in values[0].split("|"):
        clean = unquote(part).strip()
        if clean and not clean.startswith("_____"):
            parts.append(clean)
    return tuple(parts)


def same_domain(url: str, root_url: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(root_url).netloc.lower()


def url_to_markdown_relpath(url: str) -> PurePosixPath:
    parsed = urlparse(canonicalize_url(url))
    path = unquote(parsed.path or "/")
    if path in {"", "/"}:
        return PurePosixPath("_index.md")

    parts = [slugify(part) for part in path.strip("/").split("/") if part]
    if not parts:
        return PurePosixPath("_index.md")

    last = PurePosixPath(parts[-1])
    if last.suffix.lower() in HTML_SUFFIXES:
        parts[-1] = slugify(last.stem) + ".md"
        return PurePosixPath(*parts)
    if last.suffix:
        parts[-1] = slugify(last.stem) + ".md"
        return PurePosixPath(*parts)
    return PurePosixPath(*parts, "_index.md")


def source_root_name(source: str) -> str:
    if is_url(source):
        parsed = urlparse(source)
        return slugify(parsed.netloc)
    path = Path(source).resolve()
    name = path.parent.name if path.is_file() else path.name
    return slugify(name or "local-html")


def slugify(value: str) -> str:
    value = unquote(value).strip().lower()
    value = re.sub(r"[^a-z0-9а-яё._-]+", "-", value, flags=re.IGNORECASE)
    value = value.strip("-._")
    return value or "index"


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
