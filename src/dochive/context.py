from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
TERM_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{2,}")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(r"<image\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*/?>", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


@dataclass(frozen=True)
class ContextUnit:
    uri: str
    kind: str
    level: str
    path: str
    source_url: str
    title: str
    headings: tuple[str, ...]
    abstract: str
    text: str
    terms: tuple[str, ...]
    links: tuple[str, ...]
    assets: tuple[str, ...]
    content_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "kind": self.kind,
            "level": self.level,
            "path": self.path,
            "source_url": self.source_url,
            "title": self.title,
            "headings": list(self.headings),
            "abstract": self.abstract,
            "text": self.text,
            "terms": list(self.terms),
            "links": list(self.links),
            "assets": list(self.assets),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class RetrievalResult:
    unit: ContextUnit
    score: int
    why: tuple[str, ...]

    def to_dict(self, *, trace: bool = False) -> dict[str, object]:
        result = self.unit.to_dict()
        result["score"] = self.score
        if trace:
            result["why"] = list(self.why)
        return result


def build_context_index(root: Path) -> list[ContextUnit]:
    pages = _read_page_catalog(root / "_catalog" / "pages.yaml")
    units: list[ContextUnit] = []
    for page in pages:
        path = page.get("path")
        if not isinstance(path, str) or not path:
            continue
        markdown_path = root / path
        if not markdown_path.is_file() or markdown_path.suffix.lower() != ".md":
            continue
        units.extend(_units_for_markdown(root, markdown_path, page))
    return units


def write_context_index(root: Path) -> Path:
    units = build_context_index(root)
    catalog_dir = root / "_catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    index_path = catalog_dir / "context_index.jsonl"
    lines = [json.dumps(unit.to_dict(), ensure_ascii=False, sort_keys=True) for unit in units]
    index_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return index_path


def read_context_index(root: Path) -> list[ContextUnit]:
    index_path = root / "_catalog" / "context_index.jsonl"
    units: list[ContextUnit] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        units.append(_unit_from_dict(item))
    return units


def retrieve_context(root: Path, query: str, *, limit: int = 10) -> list[RetrievalResult]:
    terms = _terms(query)
    phrase = query.strip().lower()
    if not terms:
        return []
    results: list[RetrievalResult] = []
    for unit in read_context_index(root):
        score, why = _score_unit(unit, terms, phrase)
        if score <= 0:
            continue
        results.append(RetrievalResult(unit=unit, score=score, why=tuple(why)))
    results.sort(key=lambda result: (-result.score, result.unit.path, result.unit.uri))
    return results[:limit]


def retrieval_payload(root: Path, query: str, *, limit: int = 10, trace: bool = False) -> dict[str, object]:
    results = retrieve_context(root, query, limit=limit)
    return {
        "query": query,
        "root": str(root),
        "limit": limit,
        "results": [result.to_dict(trace=trace) for result in results],
    }


def _units_for_markdown(root: Path, markdown_path: Path, page: dict[str, object]) -> list[ContextUnit]:
    relpath = markdown_path.relative_to(root).as_posix()
    raw = markdown_path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _split_frontmatter(raw)
    title = _string_value(frontmatter.get("title")) or _string_value(page.get("title")) or markdown_path.stem
    source_url = _string_value(frontmatter.get("source_url")) or _string_value(page.get("source_url"))
    body = body.strip()
    page_hash = _content_hash(body)
    page_headings = tuple(heading for _, heading, _ in _heading_sections(body))
    page_abstract = _abstract(_body_without_headings(body))
    page_overview = "\n".join([line for line in [title, page_abstract] if line])
    units = [
        ContextUnit(
            uri=_mirror_uri(root, relpath),
            kind="page",
            level="L1",
            path=relpath,
            source_url=source_url,
            title=title,
            headings=page_headings,
            abstract=page_abstract,
            text=page_overview,
            terms=tuple(_terms(" ".join([page_overview, *page_headings]))),
            links=tuple(_extract_links(body)),
            assets=tuple(_extract_assets(body)),
            content_hash=page_hash,
        )
    ]
    used_slugs: dict[str, int] = {}
    for heading_level, heading, text in _heading_sections(body):
        chain = _heading_chain(body, heading_level, heading, text)
        slug = _unique_slug(_slugify(" ".join(chain) or heading), used_slugs)
        section_text = text.strip()
        units.append(
            ContextUnit(
                uri=f"{_mirror_uri(root, relpath)}#{slug}",
                kind="section",
                level="L2",
                path=relpath,
                source_url=source_url,
                title=title,
                headings=chain,
                abstract=_abstract(section_text),
                text=section_text,
                terms=tuple(_terms(" ".join([title, *chain, section_text]))),
                links=tuple(_extract_links(section_text)),
                assets=tuple(_extract_assets(section_text)),
                content_hash=_content_hash("\n".join([*chain, section_text])),
            )
        )
    return units


def _heading_sections(markdown: str) -> list[tuple[int, str, str]]:
    sections: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for line in markdown.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if current:
                sections.append(current)
            current = (len(match.group(1)), _clean_heading(match.group(2)), [])
            continue
        if current:
            current[2].append(line)
    if current:
        sections.append(current)
    return [(level, heading, "\n".join(lines)) for level, heading, lines in sections]


def _heading_chain(markdown: str, target_level: int, target_heading: str, target_text: str) -> tuple[str, ...]:
    stack: list[tuple[int, str]] = []
    found = False
    current_text_lines: list[str] = []
    for line in markdown.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if found and "\n".join(current_text_lines) == target_text:
                return tuple(heading for _, heading in stack)
            level = len(match.group(1))
            heading = _clean_heading(match.group(2))
            stack = [(item_level, item_heading) for item_level, item_heading in stack if item_level < level]
            stack.append((level, heading))
            found = level == target_level and heading == target_heading
            current_text_lines = []
            continue
        if found:
            current_text_lines.append(line)
    if found:
        return tuple(heading for _, heading in stack)
    return (target_heading,)


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    return _parse_frontmatter(match.group(1)), text[match.end() :]


def _parse_frontmatter(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    for line in text.splitlines():
        if not line or line.startswith(" ") or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        data[key] = _yaml_scalar_value(value)
    return data


def _read_page_catalog(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    pages: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_pages = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not in_pages:
            in_pages = stripped == "pages:"
            continue
        if stripped == "-":
            if current:
                pages.append(current)
            current = {}
            continue
        if current is None or not stripped or stripped in {"[]", "---"} or ": " not in stripped:
            continue
        key, value = stripped.split(": ", 1)
        current[key] = _yaml_scalar_value(value)
    if current:
        pages.append(current)
    return pages


def _yaml_scalar_value(value: str) -> object:
    value = value.strip()
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def _unit_from_dict(item: dict[str, object]) -> ContextUnit:
    return ContextUnit(
        uri=str(item.get("uri") or ""),
        kind=str(item.get("kind") or ""),
        level=str(item.get("level") or ""),
        path=str(item.get("path") or ""),
        source_url=str(item.get("source_url") or ""),
        title=str(item.get("title") or ""),
        headings=tuple(str(value) for value in item.get("headings") or []),
        abstract=str(item.get("abstract") or ""),
        text=str(item.get("text") or ""),
        terms=tuple(str(value) for value in item.get("terms") or []),
        links=tuple(str(value) for value in item.get("links") or []),
        assets=tuple(str(value) for value in item.get("assets") or []),
        content_hash=str(item.get("content_hash") or ""),
    )


def _score_unit(unit: ContextUnit, terms: list[str], phrase: str) -> tuple[int, list[str]]:
    title = unit.title.lower()
    headings = " ".join(unit.headings).lower()
    text = unit.text.lower()
    path = unit.path.lower()
    unit_terms = set(unit.terms)
    score = 0
    why: list[str] = []
    if unit.kind == "section":
        score += 10
    if phrase and len(phrase) >= 2:
        phrase_score = 0
        if phrase in title:
            phrase_score += 40
        if phrase in headings:
            phrase_score += 35
        if phrase in text:
            phrase_score += 20
        if phrase_score:
            score += phrase_score
            why.append(f"matched phrase: {phrase}")
    matched_terms: list[str] = []
    matched_headings: list[str] = []
    for term in terms:
        term_score = 0
        if term in title:
            term_score += 20
        if term in headings:
            term_score += 15
            matched_headings.append(term)
        if term in unit_terms:
            term_score += 8
        text_count = text.count(term)
        if text_count:
            term_score += min(text_count, 8) * 2
        if term in path:
            term_score += 3
        if term_score:
            score += term_score
            matched_terms.append(term)
    if matched_headings:
        why.append(f"matched heading: {', '.join(sorted(set(matched_headings)))}")
    if matched_terms:
        why.append(f"matched terms: {', '.join(sorted(set(matched_terms)))}")
    if any(term in path for term in terms):
        why.append("matched path")
    return score, why


def _terms(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in TERM_RE.findall(text.lower()):
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _extract_links(markdown: str) -> list[str]:
    return sorted({target for target in MARKDOWN_LINK_RE.findall(markdown) if not _is_asset_path(target)})


def _extract_assets(markdown: str) -> list[str]:
    assets = {target for target in MARKDOWN_LINK_RE.findall(markdown) if _is_asset_path(target)}
    assets.update(HTML_IMAGE_RE.findall(markdown))
    return sorted(assets)


def _is_asset_path(target: str) -> bool:
    suffix = target.rsplit("?", 1)[0].rsplit("#", 1)[0].lower()
    return suffix.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".webm", ".pdf"))


def _abstract(text: str, *, size: int = 220) -> str:
    plain = re.sub(r"\s+", " ", re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)).strip()
    if len(plain) <= size:
        return plain
    return plain[: size - 3].rstrip() + "..."


def _body_without_headings(markdown: str) -> str:
    return "\n".join(line for line in markdown.splitlines() if not HEADING_RE.match(line))


def _content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mirror_uri(root: Path, relpath: str) -> str:
    return f"mirror://{root.name}/{relpath}"


def _slugify(text: str) -> str:
    slug = "-".join(_terms(text))
    return slug or "section"


def _unique_slug(slug: str, used: dict[str, int]) -> str:
    count = used.get(slug, 0) + 1
    used[slug] = count
    if count == 1:
        return slug
    return f"{slug}-{count}"


def _clean_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""
