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
        return PurePosixPath("index.md")

    parts = [slugify(part) for part in path.strip("/").split("/") if part]
    if not parts:
        return PurePosixPath("index.md")

    last = PurePosixPath(parts[-1])
    if last.suffix.lower() in HTML_SUFFIXES:
        parts[-1] = slugify(last.stem) + ".md"
        return PurePosixPath(*parts)
    if last.suffix:
        parts[-1] = slugify(last.stem) + ".md"
        return PurePosixPath(*parts)
    return PurePosixPath(*parts, "index.md")


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
