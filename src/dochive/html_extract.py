from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .models import Asset
from .text_utils import repair_mojibake
from .url_utils import canonicalize_url, is_url


_HEADING_CLASS_RE = re.compile(r"(?:^|\s)H([1-6])(?:\s|$)", re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_MARKDOWN_HEADING_PARSE_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
_FOLLOWING_SNIPPET_LENGTH = 60
_LIST_ITEM_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_MARKDOWN_LINK_TEXT_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_ORPHAN_TABLE_BULLET_RE = re.compile(r"^\s*[-*+]\s+\S")
_COLWIDTH_DEFAULT = 256
_COLWIDTH_WIDE = 512
_COLWIDTH_WIDE_LEN_THRESHOLD = 80


@dataclass
class _TableCell:
    text: str
    tag: str = "td"
    rowspan: str = ""
    colspan: str = ""


@dataclass
class HtmlHeading:
    level: int
    text: str
    anchors: list[str] = field(default_factory=list)
    following_snippet: str = ""


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
        elif tag == "iframe":
            src = attrs_map.get("src", "")
            if src:
                resolved = urljoin(self.base_url, src)
                self.assets.append(Asset(source=resolved, kind="files"))
                self._markdown.append(f"\n\n[{resolved}]({resolved})\n\n")

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


def inject_html_tables(markdown: str, html: str, base_url: str) -> str:
    """Replace lossy Markdown table output with cleaned HTML tables from the source page."""

    tables = extract_html_tables(html, base_url)
    if not tables:
        return markdown

    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    table_index = 0
    while index < len(lines):
        if table_index < len(tables) and _looks_like_markdown_table_start(lines, index):
            block_start = _markdown_table_block_start(lines, index)
            end = _markdown_table_block_end(lines, index)
            if end > index:
                _drop_emitted_lines(output, index - block_start)
                if output and output[-1].strip():
                    output.append("")
                output.append(tables[table_index])
                next_line = lines[end] if end < len(lines) else ""
                if next_line.strip():
                    output.append("")
                index = end
                table_index += 1
                continue
        output.append(lines[index])
        index += 1

    if table_index == 0:
        return markdown
    result = "\n".join(output).strip() + "\n"
    result = _cleanup_madcap_table_duplicates(result)
    result = inject_html_table_section_headings(result, html)
    result = _strip_orphan_headings_between_gramax_tables(result)
    return _dedupe_adjacent_markdown_headings(result)


def extract_html_document_title(html: str) -> str:
    """Prefer the HTML document title over short crawl/nav labels for page metadata."""

    for pattern in (
        r"<title[^>]*>([^<]+)</title>",
        r"<h1\b[^>]*>(.*?)</h1>",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        text = repair_mojibake(unescape(re.sub(r"<[^>]+>", "", match.group(1)))).strip()
        if text:
            return text
    return ""


def inject_html_table_section_headings(markdown: str, html: str) -> str:
    """Insert MadCap <h2> section titles immediately before Gramax table blocks."""

    headings = _extract_h2_headings_for_html_tables(html)
    if not headings:
        return markdown

    lines = markdown.splitlines()
    output: list[str] = []
    heading_index = 0
    for line in lines:
        if line.strip().startswith('{% table header="row" %}') and heading_index < len(headings):
            heading = headings[heading_index]
            heading_index += 1
            if heading:
                if output and output[-1].strip():
                    output.append("")
                if not (output and output[-1].strip() == heading):
                    output.append(heading)
                    output.append("")
        output.append(line)
    return "\n".join(output).strip() + "\n"


def _extract_h2_headings_for_html_tables(html: str) -> list[str]:
    pending: str | None = None
    headings: list[str] = []
    for match in re.finditer(r"<h2\b[^>]*>.*?</h2>|<table\b", html, re.IGNORECASE | re.DOTALL):
        chunk = match.group(0)
        if chunk.lower().startswith("<h2"):
            text = repair_mojibake(unescape(re.sub(r"<[^>]+>", "", chunk))).strip()
            pending = f"## {text}" if text else None
            continue
        if pending:
            headings.append(pending)
            pending = None
        else:
            headings.append("")
    return headings


def _strip_orphan_headings_between_gramax_tables(markdown: str) -> str:
    """Remove duplicate MadCap h2 lines between Gramax tables (Crawl4AI + inject overlap)."""

    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        output.append(lines[index])
        if lines[index].strip() != "{% /table %}":
            index += 1
            continue
        index += 1
        gap: list[str] = []
        while index < len(lines) and not lines[index].strip().startswith('{% table header="row" %}'):
            gap.append(lines[index])
            index += 1
        prose_lines = [
            line
            for line in gap
            if line.strip()
            and not _MARKDOWN_HEADING_RE.match(line)
            and not _is_table_debris_line(line)
        ]
        heading_lines = [line for line in gap if _MARKDOWN_HEADING_RE.match(line)]
        if prose_lines:
            output.extend(gap)
            continue
        if heading_lines:
            if output and output[-1].strip():
                output.append("")
            output.append(heading_lines[-1])
            continue
        output.extend(gap)
    return "\n".join(output).strip() + "\n"


def _dedupe_adjacent_markdown_headings(markdown: str) -> str:
    output: list[str] = []
    previous_heading: str | None = None
    for line in markdown.splitlines():
        stripped = line.strip()
        if match := _MARKDOWN_HEADING_PARSE_RE.match(line):
            hashes = line.lstrip()[: line.lstrip().find(" ")]
            normalized = _normalize_heading_text(repair_mojibake(match.group(1)))
            heading_key = f"{len(hashes)}:{normalized}"
            if heading_key == previous_heading:
                continue
            previous_heading = heading_key
            output.append(line)
            continue
        if stripped:
            previous_heading = None
        output.append(line)
    return "\n".join(output).strip() + "\n"


def inject_html_comments(markdown: str, html: str) -> str:
    """Convert MadCap <p class=\"comment\"> blocks into Gramax note callouts."""

    comments = extract_html_comments(html)
    if not comments:
        return markdown

    output: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith(":::"):
            output.append(line)
            continue
        replaced = False
        for comment in comments:
            if _line_matches_comment_text(line, comment):
                output.append(":::note:false")
                output.append(comment)
                output.append(":::")
                replaced = True
                break
        if not replaced:
            output.append(line)
    return "\n".join(output).strip() + "\n"


def extract_html_tables(html: str, base_url: str) -> list[str]:
    tables: list[str] = []
    for match in re.finditer(r"<table\b.*?</table>", html, re.IGNORECASE | re.DOTALL):
        table = _sanitize_html_table(match.group(0), base_url)
        if table:
            tables.append(table)
    return tables


def _sanitize_html_table(html: str, base_url: str) -> str:
    parser = _HtmlTableParser(base_url)
    parser.feed(html)
    parser.close()
    if not parser.rows:
        return ""
    if parser.has_complex_spans:
        return _render_html_table(parser.rows)
    return _render_gramax_table(parser.rows)


def extract_html_comments(html: str) -> list[str]:
    parser = _HtmlCommentParser()
    parser.feed(html)
    parser.close()
    return parser.comments


def _looks_like_markdown_table_start(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not stripped.startswith("|") and not _is_loose_table_line(lines[index]):
        return False
    window = lines[index : min(len(lines), index + 8)]
    if any(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", line) for line in window):
        return True
    if _is_pipe_table_row(stripped) or _is_loose_table_line(lines[index]):
        return True
    return _madcap_table_region_ahead(lines, index)


def _madcap_table_region_ahead(lines: list[str], index: int) -> bool:
    for candidate in lines[index : min(len(lines), index + 24)]:
        if _is_pipe_table_row(candidate.strip()) or re.match(
            r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
            candidate,
        ):
            return True
        if candidate.strip() and re.match(r"^#{1,2}\s+", candidate.strip()):
            return False
        if candidate.strip() and not _is_table_debris_line(candidate):
            return False
    return False


def _drop_emitted_lines(output: list[str], count: int) -> None:
    while count > 0 and output:
        output.pop()
        count -= 1


def _markdown_table_block_start(lines: list[str], table_start: int) -> int:
    start = table_start
    while start > 0:
        previous = lines[start - 1]
        if not previous.strip():
            start -= 1
            continue
        if re.match(r"^#{1,2}\s+", previous.strip()):
            break
        if _is_table_debris_line(previous):
            start -= 1
            continue
        break
    return start


def _markdown_table_block_end(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if index > start and re.match(r"^##\s+", stripped):
            break
        if index > start and _is_markdown_table_boundary(stripped):
            break
        if index > start and stripped and not _is_madcap_table_zone_line(lines[index]):
            break
        index += 1
    return index


def _is_madcap_table_zone_line(line: str) -> bool:
    if _is_table_debris_line(line):
        return True
    stripped = line.strip()
    if not stripped:
        return True
    if _LIST_ITEM_PREFIX_RE.match(stripped):
        return True
    if re.match(r"^\*\*.+\*\*$", stripped):
        return True
    return line.startswith((" ", "\t"))


def _is_plain_text_between_table_blocks(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not stripped or stripped.startswith("|") or _MARKDOWN_HEADING_RE.match(stripped):
        return False
    if _ORPHAN_TABLE_BULLET_RE.match(stripped) or _LIST_ITEM_PREFIX_RE.match(stripped):
        return False
    previous = lines[index - 1].strip() if index else ""
    next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
    return previous.startswith("|") and next_line.startswith("|")


def _is_after_regular_markdown_table(lines: list[str], index: int) -> bool:
    previous = lines[index - 1].strip() if index else ""
    if not previous.startswith("|"):
        return False
    next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
    return not next_line.startswith(("|", "-", "*", "+"))


def _is_markdown_table_boundary(stripped: str) -> bool:
    if not stripped:
        return False
    return bool(
        _MARKDOWN_HEADING_RE.match(stripped)
        or stripped.startswith(("---", "***", "<image ", "<video ", "!["))
        or stripped in {"</table>", "<table>", "{% /table %}"}
        or stripped.startswith("{% table")
    )


def _is_markdown_table_continuation(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return (
        stripped.startswith("|")
        or line.startswith((" ", "\t"))
        or stripped.startswith(("- ", "* ", "+ "))
        or bool(re.match(r"^\d+\.\s+", stripped))
    )


def _is_orphan_table_bullet_line(line: str) -> bool:
    return bool(_ORPHAN_TABLE_BULLET_RE.match(line))


def _is_pipe_table_row(stripped: str) -> bool:
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_loose_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped in {"|", "| |"} or bool(re.match(r"^\|\s+\|", stripped))


def _is_table_debris_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_orphan_table_bullet_line(line):
        return True
    if _is_loose_table_line(line):
        return True
    if stripped.startswith("|"):
        return True
    return _is_pipe_table_row(stripped)


def _cleanup_madcap_table_duplicates(markdown: str) -> str:
    """Drop Crawl4AI table fragments that duplicate a preceding Gramax table."""

    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != "{% /table %}":
            output.append(line)
            index += 1
            continue
        output.append(line)
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index < len(lines) and re.match(r"^##\s+", lines[index].strip()):
            body_start = index + 1
            debris_end, found_debris = _leading_madcap_table_debris(lines, body_start)
            if found_debris:
                index = debris_end
                continue
            output.append("")
            output.append(lines[index])
            index += 1
            index = _skip_madcap_table_debris(lines, index)
            continue
        index = _skip_madcap_table_debris(lines, index)
    return "\n".join(output).strip() + "\n"


def _leading_madcap_table_debris(lines: list[str], start: int) -> tuple[int, bool]:
    """Skip blank lines, then consecutive table-debris lines; stop at real content."""

    index = start
    found_debris = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if _is_markdown_table_boundary(stripped):
            break
        if _is_table_debris_line(lines[index]):
            found_debris = True
            index += 1
            continue
        break
    return index, found_debris


def _skip_madcap_table_debris(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if _is_markdown_table_boundary(stripped):
            break
        if _is_table_debris_line(lines[index]):
            index += 1
            continue
        break
    return index


def _column_colwidths(rows: list[list[_TableCell]]) -> list[int]:
    """Gramax applies colwidth per column; use the widest cell in each column."""

    if not rows:
        return []
    num_cols = max(len(row) for row in rows)
    max_lens = [0] * num_cols
    for row in rows:
        for index, cell in enumerate(row):
            if index < num_cols:
                max_lens[index] = max(max_lens[index], len(cell.text.strip()))
    return [
        _COLWIDTH_WIDE if length >= _COLWIDTH_WIDE_LEN_THRESHOLD else _COLWIDTH_DEFAULT
        for length in max_lens
    ]


def _gramax_colwidth_directive(width: int) -> str:
    return f"{{% colwidth=[{width}] %}}"


def _render_gramax_table(rows: list[list[_TableCell]]) -> str:
    if not rows:
        return ""

    column_widths = _column_colwidths(rows)
    parts = ['{% table header="row" %}', ""]
    for row in rows:
        parts.append("---")
        parts.append("")
        for index, cell in enumerate(row):
            width = column_widths[index] if index < len(column_widths) else _COLWIDTH_DEFAULT
            parts.append(f"*  {_gramax_colwidth_directive(width)}")
            content = cell.text.strip()
            if not content:
                parts.append("   ")
            else:
                for line in content.splitlines():
                    parts.append(f"   {line}")
        parts.append("")
    parts.append("{% /table %}")
    return "\n".join(parts).strip() + "\n"


def _render_html_table(rows: list[list[_TableCell]]) -> str:
    parts = ['<table header="row">']
    for row in rows:
        parts.append("\n<tr>\n")
        for cell in row:
            attrs: list[str] = []
            if cell.rowspan:
                attrs.append(f'rowspan="{escape(cell.rowspan, quote=True)}"')
            if cell.colspan:
                attrs.append(f'colspan="{escape(cell.colspan, quote=True)}"')
            attr_str = (" " + " ".join(attrs)) if attrs else ""
            parts.append(f"\n<{cell.tag}{attr_str}>\n\n")
            if cell.text.strip():
                parts.append(cell.text.strip())
                parts.append("\n\n")
            parts.append(f"</{cell.tag}>")
        parts.append("\n</tr>\n")
    parts.append("\n</table>")
    return "".join(parts).strip() + "\n"


def _line_matches_comment_text(line: str, comment: str) -> bool:
    normalized_line = _normalize_comment_text(line)
    return bool(normalized_line and normalized_line == comment)


def _normalize_comment_text(text: str) -> str:
    stripped = repair_mojibake(text).replace("\xa0", " ").strip()
    stripped = re.sub(r"^\s*[-*+]\s+", "", stripped)
    stripped = re.sub(r"^\s*>\s+", "", stripped)
    if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
        stripped = stripped[1:-1].strip()
    if stripped.startswith("_") and stripped.endswith("_") and len(stripped) > 2:
        stripped = stripped[1:-1].strip()
    return re.sub(r"\s+", " ", stripped).strip()


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


class _HtmlTableParser(HTMLParser):
    _INLINE_TAGS = {"strong", "b", "em", "i", "code"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.rows: list[list[_TableCell]] = []
        self.column_max_lens: list[int] = []
        self.has_complex_spans = False
        self._skip_depth = 0
        self._current_row: list[_TableCell] = []
        self._in_cell = False
        self._cell_tag = "td"
        self._cell_rowspan = ""
        self._cell_colspan = ""
        self._col_index = 0
        self._cell_parts: list[str] = []
        self._in_li = False
        self._link_text: list[str] = []
        self._link_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "a":
            href = attrs_map.get("href", "").strip()
            if href:
                self._link_href = urljoin(self.base_url, href)
                self._link_text = []
            return
        if tag == "br" and self._in_cell:
            self._cell_parts.append("\n")
            return
        if tag in self._INLINE_TAGS and self._in_cell:
            self._cell_parts.append("**" if tag in {"strong", "b"} else ("`" if tag == "code" else "*"))
            return
        if tag == "tr":
            self._flush_row()
            self._col_index = 0
            return
        if tag in {"td", "th"}:
            self._finish_cell()
            self._in_cell = True
            self._cell_tag = tag
            self._cell_parts = []
            rowspan = attrs_map.get("rowspan", "").strip()
            colspan = attrs_map.get("colspan", "").strip()
            self._cell_rowspan = rowspan if rowspan.isdigit() else ""
            self._cell_colspan = colspan if colspan.isdigit() else ""
            if self._cell_rowspan or self._cell_colspan:
                self.has_complex_spans = True
            return
        if self._in_cell:
            if tag == "li":
                self._in_li = True
                self._cell_parts.append("\n- ")
                return
            if tag == "p" and self._in_li:
                return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._link_href:
            text = "".join(self._link_text).strip() or self._link_href
            self._cell_parts.append(f"[{text}]({self._link_href})")
            self._link_href = None
            self._link_text = []
            return
        if tag in self._INLINE_TAGS and self._in_cell:
            self._cell_parts.append("**" if tag in {"strong", "b"} else ("`" if tag == "code" else "*"))
            return
        if tag == "li" and self._in_cell:
            self._in_li = False
            return
        if tag in {"td", "th"}:
            self._finish_cell()
            return
        if tag == "tr":
            self._flush_row()
            return
        if tag == "table":
            self._finish_cell()
            self._flush_row()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._link_href is not None:
            self._link_text.append(data)
            return
        if self._in_cell:
            self._cell_parts.append(data)

    def _finish_cell(self) -> None:
        if not self._in_cell:
            return
        text = _normalize_table_cell_text("".join(self._cell_parts))
        while len(self.column_max_lens) <= self._col_index:
            self.column_max_lens.append(0)
        if text:
            self.column_max_lens[self._col_index] = max(self.column_max_lens[self._col_index], len(text))
        self._current_row.append(
            _TableCell(
                text=text,
                tag=self._cell_tag,
                rowspan=self._cell_rowspan,
                colspan=self._cell_colspan,
            )
        )
        self._col_index += 1
        self._cell_parts = []
        self._in_cell = False
        self._cell_rowspan = ""
        self._cell_colspan = ""

    def _flush_row(self) -> None:
        if self._current_row:
            self.rows.append(self._current_row)
            self._current_row = []


def _normalize_table_cell_text(text: str) -> str:
    text = repair_mojibake(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    compact: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line in {"-", "*", "+"} and index + 1 < len(lines) and lines[index + 1]:
            compact.append(f"- {lines[index + 1]}")
            index += 2
            continue
        if line and line not in {"-", "*", "+"}:
            compact.append(line)
        index += 1
    return "\n".join(compact).strip()


class _HtmlCommentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.comments: list[str] = []
        self._skip_depth = 0
        self._active = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "p" and _has_class_token(attrs_map, "comment"):
            self._active = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "p" and self._active:
            text = _normalize_comment_text("".join(self._parts))
            if text and text not in self.comments:
                self.comments.append(text)
            self._active = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not self._active:
            return
        self._parts.append(data)


def extract_html_headings(html: str) -> list[HtmlHeading]:
    parser = _HtmlHeadingParser()
    parser.feed(html)
    parser.close()
    return parser.headings


def extract_html_anchor_headings(html: str) -> dict[str, str]:
    parser = _HtmlAnchorHeadingParser()
    parser.feed(html)
    parser.close()
    return parser.anchor_headings


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
        self._active_heading: tuple[int, int, list[str], list[str]] | None = None
        self._awaiting_following_index: int | None = None
        self._following_tag: str | None = None
        self._following_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if self._active_heading is not None:
            level, depth, parts, anchors = self._active_heading
            attrs_map = {key.lower(): value or "" for key, value in attrs}
            if tag == "a" and not attrs_map.get("href"):
                _append_anchor(anchors, attrs_map.get("name", ""))
                _append_anchor(anchors, attrs_map.get("id", ""))
            self._active_heading = (level, depth + 1, parts, anchors)
            return

        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            anchors: list[str] = []
            _append_anchor(anchors, attrs_map.get("id", ""))
            self._active_heading = (int(tag[1]), 1, [], anchors)
            self._clear_following_capture()
            return
        if tag in {"p", "div"} and (level := _heading_level_from_class(attrs_map)):
            anchors = []
            _append_anchor(anchors, attrs_map.get("id", ""))
            self._active_heading = (level, 1, [], anchors)
            self._clear_following_capture()
            return

        self._maybe_start_following_capture(tag, attrs_map)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return

        if self._active_heading is not None:
            level, depth, parts, anchors = self._active_heading
            depth -= 1
            if depth:
                self._active_heading = (level, depth, parts, anchors)
                return

            text = _normalize_heading_text("".join(parts))
            if text:
                self.headings.append(HtmlHeading(level=level, text=text, anchors=anchors))
                self._awaiting_following_index = len(self.headings) - 1
            self._active_heading = None
            return

        self._maybe_finish_following_capture(tag)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._active_heading is not None:
            self._active_heading[2].append(data)
            return
        if self._following_tag is not None:
            self._following_parts.append(data)

    def _clear_following_capture(self) -> None:
        self._following_tag = None
        self._following_parts = []

    def _maybe_start_following_capture(self, tag: str, attrs_map: dict[str, str]) -> None:
        if self._awaiting_following_index is None or self._following_tag is not None:
            return
        if tag == "p" and not _heading_level_from_class(attrs_map):
            self._following_tag = "p"
            self._following_parts = []
        elif tag in {"ul", "ol"}:
            self._following_tag = "list"
            self._following_parts = []
        elif tag == "li" and self._following_tag == "list":
            self._following_tag = "li"
            self._following_parts = []

    def _maybe_finish_following_capture(self, tag: str) -> None:
        if self._following_tag is None:
            return
        if tag not in {self._following_tag, "ul", "ol"}:
            return
        if self._following_tag == "list" and tag not in {"li", "ul", "ol"}:
            return

        text = _normalize_heading_text("".join(self._following_parts))
        if text and self._awaiting_following_index is not None:
            self.headings[self._awaiting_following_index].following_snippet = _make_following_snippet(text)
            self._awaiting_following_index = None
        self._clear_following_capture()

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))


class _HtmlAnchorHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchor_headings: dict[str, str] = {}
        self._skip_depth = 0
        self._pending_anchors: list[str] = []
        self._active_heading: tuple[int, list[str], list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if tag == "a" and not attrs_map.get("href"):
            self._remember_anchor(attrs_map.get("name", ""))
            self._remember_anchor(attrs_map.get("id", ""))

        if self._active_heading is not None:
            depth, parts, anchors = self._active_heading
            self._active_heading = (depth + 1, parts, anchors)
            return

        is_heading = tag in {"h1", "h2", "h3", "h4", "h5", "h6"} or (
            tag in {"p", "div"} and _heading_level_from_class(attrs_map)
        )
        if is_heading:
            anchors = list(self._pending_anchors)
            self._pending_anchors = []
            if heading_id := attrs_map.get("id", ""):
                anchors.append(heading_id)
            self._active_heading = (1, [], anchors)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or self._active_heading is None:
            return

        depth, parts, anchors = self._active_heading
        depth -= 1
        if depth:
            self._active_heading = (depth, parts, anchors)
            return

        heading = _normalize_heading_text(repair_mojibake("".join(parts)))
        if heading:
            for anchor in anchors:
                if anchor and anchor not in self.anchor_headings:
                    self.anchor_headings[anchor] = heading
        self._active_heading = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._active_heading is not None:
            self._active_heading[1].append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))

    def _remember_anchor(self, value: str) -> None:
        value = value.strip()
        if value and value not in self._pending_anchors:
            self._pending_anchors.append(value)


def _heading_level_from_class(attrs_map: dict[str, str]) -> int | None:
    match = _HEADING_CLASS_RE.search(attrs_map.get("class", ""))
    return int(match.group(1)) if match else None


def _has_class_token(attrs_map: dict[str, str], token: str) -> bool:
    classes = re.split(r"\s+", attrs_map.get("class", "").strip())
    token = token.casefold()
    return any(item.casefold() == token for item in classes if item)


def _append_anchor(anchors: list[str], value: str) -> None:
    value = value.strip()
    if value and value not in anchors:
        anchors.append(value)


def _insert_missing_markdown_headings(lines: list[str], headings: list[HtmlHeading]) -> list[str]:
    output = list(lines)
    search_start = 0
    for heading in headings:
        normalized = _normalize_heading_text(repair_mojibake(heading.text))
        if not normalized:
            continue

        insertion_match = _heading_insertion_match(output, heading, search_start)
        existing_index = _find_markdown_heading(output, normalized, search_start)
        if existing_index is not None and (
            insertion_match is None or existing_index <= insertion_match[1]
        ):
            search_start = insertion_match[1] + 1 if insertion_match is not None else existing_index + 1
            continue

        if insertion_match is None:
            continue
        insertion_index, anchor_index = insertion_match
        output.insert(insertion_index, f"{'#' * heading.level} {normalized}")
        _drop_next_duplicate_heading(output, insertion_index, heading.level, normalized)
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

    snippet = _normalize_following_snippet(heading.following_snippet)
    if snippet:
        for index, line in enumerate(lines[start_index:], start=start_index):
            if _line_matches_following_snippet(line, snippet):
                return _previous_block_start(lines, index), index
    return None


def _drop_next_duplicate_heading(lines: list[str], inserted_index: int, level: int, text: str) -> None:
    for index in range(inserted_index + 1, len(lines)):
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$", lines[index])
        if not match:
            continue
        current_level = len(match.group(1))
        current_text = _normalize_heading_text(repair_mojibake(match.group(2)))
        if current_level == level and current_text == text:
            del lines[index]
        return


def _line_contains_anchor(line: str, anchor: str) -> bool:
    normalized_line = _normalize_heading_text(repair_mojibake(line))
    return anchor in normalized_line


def _is_markdown_media_line(line: str) -> bool:
    stripped = line.strip().lower()
    return stripped.startswith(("<image ", "<video "))


def _previous_block_start(lines: list[str], index: int) -> int:
    insertion = index
    cursor = index - 1
    while cursor >= 0 and not lines[cursor].strip():
        cursor -= 1
    if cursor < 0 or not _is_markdown_media_line(lines[cursor]):
        return insertion

    while cursor >= 0:
        if _is_markdown_media_line(lines[cursor]):
            insertion = cursor
            cursor -= 1
            continue
        if not lines[cursor].strip():
            cursor -= 1
            continue
        break
    return insertion


def _normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _make_following_snippet(text: str) -> str:
    normalized = _normalize_following_snippet(text)
    if len(normalized) <= _FOLLOWING_SNIPPET_LENGTH:
        return normalized
    return normalized[:_FOLLOWING_SNIPPET_LENGTH].rsplit(" ", 1)[0] or normalized[:_FOLLOWING_SNIPPET_LENGTH]


def _normalize_following_snippet(text: str) -> str:
    return _normalize_heading_text(repair_mojibake(text))


def _line_matches_following_snippet(line: str, snippet: str) -> bool:
    if not snippet:
        return False
    stripped = _LIST_ITEM_PREFIX_RE.sub("", line.strip())
    plain = _MARKDOWN_LINK_TEXT_RE.sub(r"\1", stripped)
    normalized = _normalize_following_snippet(plain)
    if not normalized:
        return False
    return snippet in normalized or normalized.startswith(snippet)


def _can_promote_markdown_line(stripped: str) -> bool:
    if not stripped or _MARKDOWN_HEADING_RE.match(stripped):
        return False
    return not stripped.startswith(("- ", "* ", "  ", "|", "!", "```"))


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def is_local_file_reference(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"", "file"}
