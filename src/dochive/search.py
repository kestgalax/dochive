from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SearchHit:
    path: Path
    score: int
    snippet: str


def search_files(root: Path, query: str, *, limit: int = 10) -> list[SearchHit]:
    terms = _query_terms(query)
    if not terms:
        return []

    hits: list[SearchHit] = []
    for path in _iter_searchable_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        score = _score(text, terms)
        if score <= 0:
            continue
        snippet_text = _markdown_body(text) if path.suffix.lower() == ".md" else text
        hits.append(SearchHit(path=path, score=score, snippet=_snippet(snippet_text, terms)))
    hits.sort(key=lambda hit: (-hit.score, str(hit.path)))
    return hits[:limit]


def _iter_searchable_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "_assets" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue
        yield path


def _query_terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{2,}", query)]


def _score(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    score = 0
    for term in terms:
        score += lowered.count(term)
    return score


def _snippet(text: str, terms: list[str], *, size: int = 220) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return text[:size].replace("\n", " ").strip()
    start = max(min(positions) - size // 3, 0)
    snippet = text[start : start + size]
    return re.sub(r"\s+", " ", snippet).strip()


def _markdown_body(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()
