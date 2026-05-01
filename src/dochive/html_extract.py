from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .models import Asset
from .text_utils import repair_mojibake
from .url_utils import canonicalize_url, is_url


_HEADING_CLASS_RE = re.compile(r"(?:^|\s)H([1-6])(?:\s|$)", re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_MARKDOWN_HEADING_PARSE_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")


@dataclass
class HtmlHeading:
    level: int
    text: str
    anchors: list[str] = field(default_factory=list)


class HtmlDocumentParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.links: list[tuple[str, str]] = []
        self.assets: list[Asset] = []
        self._title_parts: list[str] = []
        self._current_link: str | None = None
        self._current_link_text: list[str] = []
        self._skip_depth = 0
        self._markdown: list[str] = []
        self._list_depth = 0
        self._pre_depth = 0
        self._video_depth = 0
        self._current_video_sources: list[str] = []

    @property
    def markdown(self) -> str:
        text = "".join(self._markdown)
        lines = [line.rstrip() for line in text.splitlines()]
        compact: list[str] = []
        blank = False
        for line in lines:
            if not line.strip():
                if not blank:
                    compact.append("")
                blank = True
            else:
                compact.append(line)
                blank = False
        return "\n".join(compact).strip() + "\n"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag == "meta" and attrs_map.get("name", "").lower() == "description":
            self.description = attrs_map.get("content", "")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self._markdown.append("\n\n" + ("#" * level) + " ")
        elif tag in {"p", "div"} and (level := _heading_level_from_class(attrs_map)):
            self._markdown.append("\n\n" + ("#" * level) + " ")
        elif tag == "p":
            self._markdown.append("\n\n")
        elif tag == "br":
            self._markdown.append("  \n")
        elif tag == "pre":
            self._pre_depth += 1
            self._markdown.append("\n\n```\n")
        elif tag == "code" and not self._pre_depth:
            self._markdown.append("`")
        elif tag in {"strong", "b"}:
            self._markdown.append("**")
        elif tag in {"em", "i"}:
            self._markdown.append("*")
        elif tag in {"ul", "ol"}:
            self._list_depth += 1
            self._markdown.append("\n")
        elif tag == "li":
            self._markdown.append("\n" + ("  " * max(self._list_depth - 1, 0)) + "- ")
        elif tag == "a":
            href = attrs_map.get("href", "")
            if href:
                resolved = urljoin(self.base_url, href)
                self._current_link = canonicalize_url(resolved) if is_url(resolved) else resolved
                self._current_link_text = []
        elif tag == "img":
            src = attrs_map.get("src", "")
            alt = attrs_map.get("alt", "")
            if src:
                resolved = urljoin(self.base_url, src)
                self.assets.append(Asset(source=resolved, kind="images", alt=alt))
                self._markdown.append(f"![{alt}]({resolved})")
        elif tag == "video":
            src = attrs_map.get("src", "")
            self._video_depth += 1
            if src:
                resolved = urljoin(self.base_url, src)
                self.assets.append(Asset(source=resolved, kind="videos"))
                self._current_video_sources.append(resolved)
        elif tag == "source":
            src = attrs_map.get("src", "")
            if src:
                kind = "videos" if self._video_depth else "files"
                resolved = urljoin(self.base_url, src)
                self.assets.append(Asset(source=resolved, kind=kind))
                if self._video_depth:
                    self._current_video_sources.append(resolved)
        elif tag == "audio":
            src = attrs_map.get("src", "")
            if src:
                self.assets.append(Asset(source=urljoin(self.base_url, src), kind="files"))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self.title = unescape("".join(self._title_parts)).strip()
        elif tag == "a" and self._current_link:
            text = "".join(self._current_link_text).strip() or self._current_link
            self.links.append((self._current_link, text))
            self._markdown.append(f"[{text}]({self._current_link})")
            self._current_link = None
            self._current_link_text = []
        elif tag == "pre" and self._pre_depth:
            self._pre_depth -= 1
            self._markdown.append("\n```\n")
        elif tag == "code" and not self._pre_depth:
            self._markdown.append("`")
        elif tag in {"strong", "b"}:
            self._markdown.append("**")
        elif tag in {"em", "i"}:
            self._markdown.append("*")
        elif tag in {"ul", "ol"} and self._list_depth:
            self._list_depth -= 1
            self._markdown.append("\n")
        elif tag == "video" and self._video_depth:
            self._video_depth -= 1
            if not self._video_depth and self._current_video_sources:
                self._markdown.append("\n\n" + _render_video(self._current_video_sources) + "\n\n")
                self._current_video_sources = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._video_depth:
            return
        if self.lasttag == "title":
            self._title_parts.append(data)
            return
        if self._current_link is not None:
            self._current_link_text.append(data)
            return
        self._markdown.append(data)


def parse_html_document(html: str, base_url: str) -> HtmlDocumentParser:
    parser = HtmlDocumentParser(base_url)
    parser.feed(html)
    parser.close()
    return parser


def inject_html_videos(markdown: str, html: str, base_url: str) -> str:
    """Render HTML video tags that Markdown extractors often replace with fallback text."""

    if "<video" in markdown.lower():
        return markdown
    videos = extract_html_videos(html, base_url)
    if not videos:
        return markdown

    output: list[str] = []
    video_index = 0
    for line in markdown.splitlines():
        if video_index < len(videos) and _is_video_fallback_line(line):
            output.append(_render_video(videos[video_index]))
            video_index += 1
        else:
            output.append(line)
    return "\n".join(output)


def extract_html_videos(html: str, base_url: str) -> list[list[str]]:
    parser = _HtmlVideoParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.videos


def _render_video(sources: list[str]) -> str:
    return f'<video path="{sources[0]}"/>'


def _is_video_fallback_line(line: str) -> bool:
    normalized = line.strip().lower()
    return normalized in {
        "your browser does not support the video tag.",
        "your browser does not support html5 video.",
        "your browser does not support the html5 video tag.",
    }


class _HtmlVideoParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.videos: list[list[str]] = []
        self._depth = 0
        self._sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "video":
            if not self._depth:
                self._sources = []
            self._depth += 1
            if src := attrs_map.get("src", ""):
                self._sources.append(urljoin(self.base_url, src))
        elif tag == "source" and self._depth:
            if src := attrs_map.get("src", ""):
                self._sources.append(urljoin(self.base_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag != "video" or not self._depth:
            return
        self._depth -= 1
        if not self._depth and self._sources:
            self.videos.append(list(dict.fromkeys(self._sources)))
            self._sources = []


def extract_html_headings(html: str) -> list[HtmlHeading]:
    parser = _HtmlHeadingParser()
    parser.feed(html)
    parser.close()
    return parser.headings


def promote_markdown_headings(markdown: str, html: str) -> str:
    """Restore Markdown heading markers from source HTML when an extractor drops them."""

    headings = extract_html_headings(html)
    heading_levels: dict[str, int] = {}
    for heading in headings:
        normalized = _normalize_heading_text(repair_mojibake(heading.text))
        if normalized and normalized not in heading_levels:
            heading_levels[normalized] = heading.level
    if not heading_levels:
        return markdown

    output: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if match := _MARKDOWN_HEADING_PARSE_RE.match(line):
            normalized = _normalize_heading_text(repair_mojibake(match.group(1)))
            level = heading_levels.get(normalized)
            output.append(f"{'#' * level} {normalized}" if level else line)
            continue

        normalized = _normalize_heading_text(repair_mojibake(stripped))
        level = heading_levels.get(normalized)
        if level and _can_promote_markdown_line(stripped):
            output.append(f"{'#' * level} {normalized}")
        else:
            output.append(line)
    return "\n".join(_insert_missing_markdown_headings(output, headings))


class _HtmlHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[HtmlHeading] = []
        self._skip_depth = 0
        self._active_heading: tuple[int, int, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if self._active_heading is not None:
            level, depth, parts = self._active_heading
            self._active_heading = (level, depth + 1, parts)
            return

        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._active_heading = (int(tag[1]), 1, [])
        elif tag in {"p", "div"} and (level := _heading_level_from_class(attrs_map)):
            self._active_heading = (level, 1, [])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or self._active_heading is None:
            return

        level, depth, parts = self._active_heading
        depth -= 1
        if depth:
            self._active_heading = (level, depth, parts)
            return

        text = _normalize_heading_text("".join(parts))
        if text:
            self.headings.append(HtmlHeading(level=level, text=text))
        self._active_heading = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._active_heading is not None:
            self._active_heading[2].append(data)
            return
        if self.headings:
            anchor = _normalize_heading_text(repair_mojibake(data))
            if anchor and len(self.headings[-1].anchors) < 20:
                self.headings[-1].anchors.append(anchor)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))


def _heading_level_from_class(attrs_map: dict[str, str]) -> int | None:
    match = _HEADING_CLASS_RE.search(attrs_map.get("class", ""))
    return int(match.group(1)) if match else None


def _insert_missing_markdown_headings(lines: list[str], headings: list[HtmlHeading]) -> list[str]:
    output = list(lines)
    search_start = 0
    for heading in headings:
        normalized = _normalize_heading_text(repair_mojibake(heading.text))
        if not normalized:
            continue

        insertion_match = _heading_insertion_match(output, heading, search_start)
        existing_index = _find_markdown_heading(output, normalized, search_start)
        if existing_index is not None:
            search_start = existing_index + 1
            continue

        if insertion_match is None:
            continue
        insertion_index, anchor_index = insertion_match
        output.insert(insertion_index, f"{'#' * heading.level} {normalized}")
        search_start = anchor_index + 2
    return output


def _find_markdown_heading(lines: list[str], text: str, start_index: int) -> int | None:
    for index, line in enumerate(lines[start_index:], start=start_index):
        if match := _MARKDOWN_HEADING_PARSE_RE.match(line):
            if _normalize_heading_text(repair_mojibake(match.group(1))) == text:
                return index
    return None


def _heading_insertion_match(lines: list[str], heading: HtmlHeading, start_index: int = 0) -> tuple[int, int] | None:
    for anchor in heading.anchors:
        normalized_anchor = _normalize_heading_text(repair_mojibake(anchor))
        if not normalized_anchor:
            continue
        for index, line in enumerate(lines[start_index:], start=start_index):
            if _line_contains_anchor(line, normalized_anchor):
                return _previous_block_start(lines, index), index
    return None


def _line_contains_anchor(line: str, anchor: str) -> bool:
    normalized_line = _normalize_heading_text(repair_mojibake(line))
    return anchor in normalized_line


def _previous_block_start(lines: list[str], index: int) -> int:
    return index


def _normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _can_promote_markdown_line(stripped: str) -> bool:
    if not stripped or _MARKDOWN_HEADING_RE.match(stripped):
        return False
    return not stripped.startswith(("- ", "* ", "  ", "|", "!", "```"))


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def is_local_file_reference(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"", "file"}
