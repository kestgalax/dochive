from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Asset:
    source: str
    kind: str
    alt: str = ""
    local_path: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class Page:
    source_url: str
    canonical_url: str
    title: str
    markdown: str
    depth: int
    description: str = ""
    content_type: str = "text/html"
    status_code: int = 200
    parent_url: str | None = None
    links_internal: list[str] = field(default_factory=list)
    links_external: list[str] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    source_path: Path | None = None


@dataclass(frozen=True)
class MirrorIssue:
    kind: str
    message: str
    url: str | None = None
    path: str | None = None
    source: str | None = None
    severity: str = "warning"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "severity": self.severity,
            "kind": self.kind,
            "message": self.message,
            "url": self.url,
            "path": self.path,
            "source": self.source,
        }


@dataclass
class MirrorRun:
    pages: list[Page] = field(default_factory=list)
    issues: list[MirrorIssue] = field(default_factory=list)


@dataclass(frozen=True)
class MirrorConfig:
    source: str
    out_dir: Path
    max_depth: int = 3
    max_pages: int = 500
    render_js: bool = False
    save_asset_kinds: frozenset[str] = frozenset()
    include_external: bool = False
    respect_robots_txt: bool = True
    scope: str = "subtree"
    include_url_prefixes: tuple[str, ...] = ()
    content_selector: str | None = None
    exclude_selector: str | None = None
    exclude_tags: tuple[str, ...] = ("script", "style", "noscript")
    clean_markdown: bool = True
    noise_lines: tuple[str, ...] = ()
    image_link_mode: str = "plain"
    image_render_mode: str = "html"
    image_size_mode: str = "intrinsic"
    image_max_width: int | None = None
    anti_bot_mode: str = "basic"
