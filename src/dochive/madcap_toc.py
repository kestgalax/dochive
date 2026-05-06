from __future__ import annotations

import ast
import re
import ssl
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import quote, urljoin, urlparse
from urllib.request import urlopen
from xml.etree import ElementTree

from .models import MirrorConfig, MirrorIssue, StructureEntry, StructureRun
from .text_utils import repair_mojibake
from .url_utils import canonicalize_url

try:
    import certifi
except ImportError:  # pragma: no cover - fallback for minimal embedded environments
    certifi = None


DEFINE_RE = re.compile(r"^\s*define\((.*)\)\s*;?\s*$", re.DOTALL)
UNQUOTED_KEY_RE = re.compile(r"(?<=[{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:")


@dataclass
class MadCapTocNode:
    id: int
    title: str
    url: str
    children: list["MadCapTocNode"] = field(default_factory=list)


def discover_madcap_structure(config: MirrorConfig) -> StructureRun:
    root_url = madcap_output_root_url(config.source)
    help_system_url = urljoin(root_url, "Data/HelpSystem.xml")
    try:
        help_system = _fetch_text(help_system_url)
        toc_path = help_system_toc_path(help_system)
        toc_url = urljoin(root_url, toc_path)
        toc = parse_toc_js(_fetch_text(toc_url))
        chunk_metadata: dict[int, tuple[str, str]] = {}
        for index in range(toc["numchunks"]):
            chunk_url = urljoin(toc_url, f"{toc['prefix']}{index}.js")
            chunk_metadata.update(parse_toc_chunk_js(_fetch_text(chunk_url)))
        roots = build_toc_nodes(toc["tree"], chunk_metadata)
    except Exception as exc:
        return StructureRun(
            issues=[
                MirrorIssue(
                    kind="madcap_toc_unavailable",
                    message=str(exc),
                    url=help_system_url,
                    severity="error",
                )
            ]
        )

    selected = select_toc_roots(roots, config.source, root_url=root_url, scope=config.scope)
    entries = toc_nodes_to_structure_entries(selected, root_url=root_url)
    return StructureRun(entries=entries)


def madcap_output_root_url(source: str) -> str:
    parsed = urlparse(source)
    parts = [part for part in parsed.path.split("/") if part]
    lowered = [part.lower() for part in parts]
    if "content" in lowered:
        root_parts = parts[: lowered.index("content")]
        root_path = "/" + "/".join(root_parts) + "/"
        return parsed._replace(path=root_path, params="", query="", fragment="").geturl()
    path = parsed.path
    if not path.endswith("/"):
        path = path.rsplit("/", 1)[0] + "/"
    return parsed._replace(path=path, params="", query="", fragment="").geturl()


def help_system_toc_path(xml: str) -> str:
    root = ElementTree.fromstring(xml)
    toc_path = root.attrib.get("Toc", "")
    if not toc_path:
        raise ValueError("HelpSystem.xml does not declare a Toc attribute.")
    return toc_path


def parse_toc_js(text: str) -> dict[str, object]:
    data = _parse_define_object(text)
    if not isinstance(data, dict):
        raise ValueError("MadCap TOC JS did not contain an object.")
    numchunks = data.get("numchunks")
    prefix = data.get("prefix")
    tree = data.get("tree")
    if not isinstance(numchunks, int) or not isinstance(prefix, str) or not isinstance(tree, dict):
        raise ValueError("MadCap TOC JS is missing numchunks, prefix, or tree.")
    return {"numchunks": numchunks, "prefix": prefix, "tree": tree}


def parse_toc_chunk_js(text: str) -> dict[int, tuple[str, str]]:
    data = _parse_define_object(text)
    if not isinstance(data, dict):
        raise ValueError("MadCap TOC chunk JS did not contain an object.")
    metadata: dict[int, tuple[str, str]] = {}
    for raw_url, item in data.items():
        if not isinstance(raw_url, str) or not isinstance(item, dict):
            continue
        ids = item.get("i")
        titles = item.get("t")
        if not isinstance(ids, list) or not isinstance(titles, list):
            continue
        for index, raw_id in enumerate(ids):
            if not isinstance(raw_id, int) or index >= len(titles):
                continue
            title = clean_madcap_title(str(titles[index]))
            metadata[raw_id] = (raw_url, title)
    return metadata


def build_toc_nodes(tree: dict[str, object], metadata: dict[int, tuple[str, str]]) -> list[MadCapTocNode]:
    raw_nodes = tree.get("n")
    if not isinstance(raw_nodes, list):
        raise ValueError("MadCap TOC tree has no node list.")
    return [_build_toc_node(raw_node, metadata) for raw_node in raw_nodes if isinstance(raw_node, dict)]


def select_toc_roots(
    roots: list[MadCapTocNode],
    source: str,
    *,
    root_url: str,
    scope: str,
) -> list[MadCapTocNode]:
    source_url = canonicalize_url(source)
    if scope != "subtree" or _is_main_page_url(source):
        return roots
    node = _find_node_by_canonical_url(roots, source_url, root_url=root_url)
    return [node] if node else roots


def toc_nodes_to_structure_entries(
    roots: list[MadCapTocNode],
    *,
    root_url: str,
) -> list[StructureEntry]:
    entries: list[StructureEntry] = []
    order = 1

    def visit(node: MadCapTocNode, path: tuple[str, ...], parent_url: str | None, depth: int) -> None:
        nonlocal order
        absolute_url = canonicalize_url(_toc_absolute_url(root_url, node.url))
        nav_path = (*path, node.title)
        entries.append(
            StructureEntry(
                canonical_url=absolute_url,
                fetch_url=_toc_fetch_url(absolute_url, nav_path),
                title=node.title,
                depth=depth,
                order=order,
                nav_parent_url=parent_url,
                nav_path=nav_path,
                placeholder=True,
            )
        )
        order += 1
        for child in node.children:
            visit(child, nav_path, absolute_url, depth + 1)

    for root in roots:
        visit(root, (), None, 0)
    return entries


def clean_madcap_title(value: str) -> str:
    value = repair_mojibake(unescape(value)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _fetch_text(url: str) -> str:
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
    with urlopen(url, timeout=30, context=context) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def _parse_define_object(text: str) -> object:
    match = DEFINE_RE.match(text)
    if not match:
        raise ValueError("MadCap JS file is not wrapped in define(...).")
    literal = UNQUOTED_KEY_RE.sub(lambda item: f' "{item.group(1)}":', match.group(1))
    return ast.literal_eval(literal)


def _build_toc_node(raw_node: dict[str, object], metadata: dict[int, tuple[str, str]]) -> MadCapTocNode:
    raw_id = raw_node.get("i")
    if not isinstance(raw_id, int):
        raise ValueError("MadCap TOC node is missing an integer id.")
    url, title = metadata.get(raw_id, ("", f"#{raw_id}"))
    children = [
        _build_toc_node(child, metadata)
        for child in raw_node.get("n", [])
        if isinstance(child, dict)
    ]
    return MadCapTocNode(id=raw_id, title=title, url=url, children=children)


def _find_node_by_canonical_url(
    nodes: list[MadCapTocNode],
    source_url: str,
    *,
    root_url: str,
) -> MadCapTocNode | None:
    for node in nodes:
        if canonicalize_url(_toc_absolute_url(root_url, node.url)) == source_url:
            return node
        found = _find_node_by_canonical_url(node.children, source_url, root_url=root_url)
        if found:
            return found
    return None


def _is_main_page_url(url: str) -> bool:
    return urlparse(url).path.rsplit("/", 1)[-1].lower() in {"main_page.htm", "main_page.html", "main_page.xhtml"}


def _toc_fetch_url(url: str, nav_path: tuple[str, ...]) -> str:
    if not nav_path:
        return url
    tocpath = quote("|".join((*nav_path, "_____0")), safe="")
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}TocPath={tocpath}"


def _toc_absolute_url(root_url: str, toc_url: str) -> str:
    return urljoin(root_url, toc_url.lstrip("/"))
