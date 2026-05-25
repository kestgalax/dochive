from __future__ import annotations

import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from .html_extract import _sanitize_html_table, parse_html_document
from .models import Asset
from .url_utils import canonicalize_confluence_url, canonicalize_url, is_url


def confluence_body_html(html: str) -> str:
    main = _extract_first_element(html, lambda _tag, attrs: attrs.get("id") == "main-content")
    if main:
        body = _extract_first_element(main, lambda _tag, attrs: _has_class(attrs, "wiki-content"))
        if body:
            return body
    body = _extract_first_element(html, lambda _tag, attrs: _has_class(attrs, "wiki-content"))
    return body or html


def confluence_markdown(html: str, base_url: str) -> str:
    parts: list[str] = []
    last_end = 0
    for match in re.finditer(r"<table\b.*?</table>", html, re.IGNORECASE | re.DOTALL):
        before = _segment_markdown(html[last_end : match.start()], base_url)
        if before:
            parts.append(before)
        table = _render_confluence_table(match.group(0), base_url)
        if table:
            parts.append(table)
        last_end = match.end()

    tail = _segment_markdown(html[last_end:], base_url)
    if tail:
        parts.append(tail)
    return "\n\n".join(part.strip() for part in parts if part.strip()).strip() + "\n"


def confluence_links_and_assets(html: str, base_url: str) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    parser = _ConfluenceLinkMediaParser(base_url)
    parser.feed(html)
    parser.close()
    links = {
        "internal": [{"href": href, "text": text} for href, text in parser.links],
        "external": [],
    }
    media: dict[str, list[dict[str, str]]] = {}
    for asset in parser.assets:
        media.setdefault(asset.kind, []).append({"src": asset.source, "alt": asset.alt})
    return links, media


def _segment_markdown(html: str, base_url: str) -> str:
    if not html.strip():
        return ""
    return parse_html_document(html, base_url).markdown.strip()


def _render_confluence_table(html: str, base_url: str) -> str:
    parser = _SimpleTableParser(base_url)
    parser.feed(html)
    parser.close()
    if parser.is_simple and parser.rows:
        return _markdown_table(parser.rows)
    return _sanitize_html_table(html, base_url)


def _markdown_table(rows: list[list[str]]) -> str:
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header, body = padded[0], padded[1:]
    lines = [
        "| " + " | ".join(_escape_table_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def _escape_table_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\n", "<br>")).strip().replace("|", r"\|")


class _SimpleTableParser(HTMLParser):
    _UNSUPPORTED = {"table", "pre", "blockquote", "ul", "ol", "li", "div", "p"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.rows: list[list[str]] = []
        self.is_simple = True
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._cell_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "tr":
            self._current_row = []
            return
        if tag in {"td", "th"}:
            if attrs_map.get("rowspan") or attrs_map.get("colspan"):
                self.is_simple = False
            self._current_cell = []
            self._cell_depth = 1
            return
        if self._current_cell is None:
            return
        if tag == "a":
            href = attrs_map.get("href", "").strip()
            if href:
                self._link_href = urljoin(self.base_url, href)
                self._link_text = []
            return
        if tag == "br":
            self._current_cell.append("<br>")
            return
        if tag in {"strong", "b"}:
            self._current_cell.append("**")
            return
        if tag == "code":
            self._current_cell.append("`")
            return
        if tag in {"em", "i"}:
            self._current_cell.append("*")
            return
        if tag in self._UNSUPPORTED:
            self.is_simple = False
        self._cell_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._link_href:
            text = "".join(self._link_text).strip() or self._link_href
            self._current_cell_text(f"[{text}]({self._link_href})")
            self._link_href = None
            self._link_text = []
            return
        if self._current_cell is not None and tag in {"strong", "b"}:
            self._current_cell.append("**")
            return
        if self._current_cell is not None and tag == "code":
            self._current_cell.append("`")
            return
        if self._current_cell is not None and tag in {"em", "i"}:
            self._current_cell.append("*")
            return
        if tag in {"td", "th"} and self._current_cell is not None:
            if self._current_row is not None:
                self._current_row.append(_clean_cell_text("".join(self._current_cell)))
            self._current_cell = None
            self._cell_depth = 0
            return
        if tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
            return
        if self._current_cell is not None and self._cell_depth:
            self._cell_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._link_href is not None:
            self._link_text.append(data)
            return
        self._current_cell_text(data)

    def _current_cell_text(self, text: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(text)


def _clean_cell_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value).replace("\xa0", " ")).strip()


class _ConfluenceLinkMediaParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self.assets: list[Asset] = []
        self._skip_depth = 0
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            href = attrs_map.get("href", "").strip()
            if href:
                self._link_href = _canonicalize_link(href, self.base_url)
                self._link_text = []
        elif tag == "img":
            src = attrs_map.get("src", "").strip()
            if src:
                self.assets.append(Asset(source=urljoin(self.base_url, src), kind="images", alt=attrs_map.get("alt", "")))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._link_href:
            text = re.sub(r"\s+", " ", "".join(self._link_text)).strip() or self._link_href
            self.links.append((self._link_href, text))
            self._link_href = None
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._link_href is not None:
            self._link_text.append(data)


def _canonicalize_link(href: str, base_url: str) -> str:
    absolute = urljoin(base_url, href)
    if not is_url(absolute):
        return absolute
    if "viewpage.action" in absolute:
        return canonicalize_confluence_url(absolute)
    return canonicalize_url(absolute)


def _extract_first_element(html: str, predicate: object) -> str:
    parser = _ElementExtractor(predicate)  # type: ignore[arg-type]
    parser.feed(html)
    parser.close()
    return parser.html


class _ElementExtractor(HTMLParser):
    def __init__(self, predicate) -> None:  # type: ignore[no-untyped-def]
        super().__init__(convert_charrefs=False)
        self.predicate = predicate
        self.html = ""
        self._depth = 0
        self._parts: list[str] = []
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if self._depth or self.predicate(tag.lower(), attrs_map):
            self._parts.append(_start_tag(tag, attrs, closed=False))
            self._depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if self._depth or self.predicate(tag.lower(), attrs_map):
            self._parts.append(_start_tag(tag, attrs, closed=True))

    def handle_endtag(self, tag: str) -> None:
        if not self._depth or self._done:
            return
        self._parts.append(f"</{tag}>")
        self._depth -= 1
        if not self._depth:
            self.html = "".join(self._parts)
            self._done = True

    def handle_data(self, data: str) -> None:
        if self._depth and not self._done:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._depth and not self._done:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._depth and not self._done:
            self._parts.append(f"&#{name};")


def _start_tag(tag: str, attrs: list[tuple[str, str | None]], *, closed: bool) -> str:
    rendered_attrs = "".join(
        f' {name}="{escape(value, quote=True)}"' if value is not None else f" {name}"
        for name, value in attrs
    )
    return f"<{tag}{rendered_attrs}{' /' if closed else ''}>"


def _has_class(attrs: dict[str, str], class_name: str) -> bool:
    return class_name in attrs.get("class", "").split()
