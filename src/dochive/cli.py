from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .local_source import crawl_local_html
from .models import MirrorConfig
from .publish import publish_mirror
from .search import search_files
from .url_utils import is_url
from .web_source import build_web_structure, crawl_web
from .writer import write_mirror, write_structure_catalog


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "mirror":
        return mirror_command(args)
    if args.command == "structure":
        return structure_command(args)
    if args.command == "catalog":
        return catalog_command(args)
    if args.command == "query":
        return query_command(args)
    if args.command == "publish":
        return publish_command(args)
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dochive", description="Mirror HTML docs into Markdown + YAML indexes.")
    subparsers = parser.add_subparsers(dest="command")

    mirror = subparsers.add_parser("mirror", help="Crawl/mirror documentation into Markdown.")
    mirror.add_argument("--source", required=True, help="Start URL, local HTML file, or local HTML directory.")
    mirror.add_argument("--out", required=True, type=Path, help="Output directory.")
    mirror.add_argument("--max-depth", type=int, default=3)
    mirror.add_argument("--max-pages", type=int, default=500)
    mirror.add_argument("--render-js", action="store_true", help="Use browser rendering for web sources.")
    mirror.add_argument("--include-external", action="store_true", help="Keep external crawl targets eligible. Reserved for later.")
    mirror.add_argument(
        "--scope",
        choices=("subtree", "domain"),
        default="subtree",
        help="For URL sources, restrict crawling to the start URL directory subtree or the whole domain.",
    )
    mirror.add_argument(
        "--include-url-prefix",
        action="append",
        default=[],
        help="Additional URL prefix allowed for crawling. Can be passed multiple times.",
    )
    mirror.add_argument("--ignore-robots", action="store_true", help="Do not respect robots.txt. Reserved for later.")
    mirror.add_argument(
        "--save-assets",
        default="",
        help="Comma-separated asset kinds to download/copy, e.g. images,files,videos. Empty means catalog only.",
    )
    mirror.add_argument("--content-selector", help="CSS selector for the main content area when crawling web pages.")
    mirror.add_argument("--exclude-selector", help="CSS selector to exclude before Markdown generation.")
    mirror.add_argument(
        "--exclude-tag",
        action="append",
        default=[],
        help="HTML tag to exclude during web extraction. Can be passed multiple times.",
    )
    mirror.add_argument(
        "--noise-line",
        action="append",
        default=[],
        help="Exact Markdown line to remove during cleanup. Can be passed multiple times.",
    )
    mirror.add_argument("--no-clean-markdown", action="store_true", help="Disable Markdown post-cleanup.")
    mirror.add_argument(
        "--image-link-mode",
        choices=("plain", "linked"),
        default="plain",
        help="How to render linked images. `plain` writes one image; `linked` keeps [![](thumb)](full).",
    )
    mirror.add_argument(
        "--image-render-mode",
        choices=("html", "markdown"),
        default="html",
        help="How to render plain images. `html` writes Gramax <image src=\"...\"/>; `markdown` writes ![](...).",
    )
    mirror.add_argument(
        "--image-size-mode",
        choices=("intrinsic", "max-width", "none"),
        default="intrinsic",
        help="How to size HTML images. `intrinsic` writes width/height; `max-width` writes responsive style; `none` omits sizes.",
    )
    mirror.add_argument("--image-max-width", type=int, help="Maximum rendered width in pixels for --image-size-mode max-width.")
    mirror.add_argument(
        "--anti-bot",
        choices=("off", "basic", "stealth", "aggressive"),
        default="basic",
        help=(
            "Crawl4AI anti-bot profile for web sources. `basic` is the default; "
            "`stealth` and `aggressive` are reserved for future proxy/undetected-browser support."
        ),
    )
    mirror.add_argument(
        "--structure-mode",
        choices=("auto", "toc", "links"),
        default="auto",
        help=(
            "How to discover web documentation structure. `auto` uses a MadCap TOC when available, "
            "`toc` requires it, and `links` uses link crawling."
        ),
    )

    structure = subparsers.add_parser("structure", help="Discover and save a web documentation structure.")
    structure.add_argument("--source", required=True, help="Start URL for structure discovery.")
    structure.add_argument("--out", required=True, type=Path, help="Output directory.")
    structure.add_argument("--max-depth", type=int, default=3)
    structure.add_argument("--max-pages", type=int, default=500)
    structure.add_argument(
        "--scope",
        choices=("subtree", "domain"),
        default="subtree",
        help="Restrict discovery to the start URL directory subtree or the whole domain.",
    )
    structure.add_argument(
        "--include-url-prefix",
        action="append",
        default=[],
        help="Additional URL prefix allowed for discovery. Can be passed multiple times.",
    )
    structure.add_argument("--content-selector", help="CSS selector for the main content area when crawling web pages.")
    structure.add_argument("--exclude-selector", help="CSS selector to exclude before navigation extraction.")
    structure.add_argument(
        "--exclude-tag",
        action="append",
        default=[],
        help="HTML tag to exclude during web extraction. Can be passed multiple times.",
    )
    structure.add_argument(
        "--anti-bot",
        choices=("off", "basic", "stealth", "aggressive"),
        default="basic",
        help=(
            "Crawl4AI anti-bot profile for web sources. `basic` is the default; "
            "`stealth` and `aggressive` are reserved for future proxy/undetected-browser support."
        ),
    )
    structure.add_argument(
        "--structure-mode",
        choices=("auto", "toc", "links"),
        default="auto",
        help=(
            "How to discover web documentation structure. `auto` uses a MadCap TOC when available, "
            "`toc` requires it, and `links` uses link crawling."
        ),
    )

    catalog = subparsers.add_parser("catalog", help="Show catalog file locations for a mirror.")
    catalog.add_argument("--root", required=True, type=Path, help="Mirror root directory.")

    query = subparsers.add_parser("query", help="Search a mirrored Markdown knowledge base without vectors.")
    query.add_argument("--root", required=True, type=Path, help="Mirror root directory.")
    query.add_argument("--text", required=True, help="Search query.")
    query.add_argument("--limit", type=int, default=10, help="Maximum number of hits.")

    publish = subparsers.add_parser("publish", help="Commit and optionally push a mirror directory with Git.")
    publish.add_argument("--root", required=True, type=Path, help="Mirror root directory or Git worktree.")
    publish.add_argument("--message", default="Update documentation mirror", help="Commit message.")
    publish.add_argument("--dry-run", action="store_true", help="Show Git actions without changing anything.")
    publish.add_argument("--init", action="store_true", help="Initialize Git in --root when it is not a worktree.")
    publish.add_argument("--push", action="store_true", help="Run git push after a successful commit.")
    return parser


def mirror_command(args: argparse.Namespace) -> int:
    config = _mirror_config_from_args(args)

    try:
        run = crawl_web(config) if is_url(config.source) else crawl_local_html(config)
        root = write_mirror(run.pages, config, issues=run.issues)
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Mirrored {len(run.pages)} pages into {root}")
    if run.issues:
        print(f"Issues: {len(run.issues)}")
    print(f"Catalog: {root / '_catalog' / 'pages.yaml'}")
    print(f"Summary: {root / '_catalog' / 'summary.yaml'}")
    print(f"Errors: {root / '_catalog' / 'errors.yaml'}")
    return 0


def structure_command(args: argparse.Namespace) -> int:
    if not is_url(args.source):
        print("error: `dochive structure` currently supports URL sources only.", file=sys.stderr)
        return 2
    config = MirrorConfig(
        source=args.source,
        out_dir=args.out,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        scope=args.scope,
        include_url_prefixes=tuple(args.include_url_prefix),
        content_selector=args.content_selector,
        exclude_selector=args.exclude_selector,
        exclude_tags=tuple(args.exclude_tag) if args.exclude_tag else ("script", "style", "noscript"),
        anti_bot_mode=args.anti_bot,
        structure_mode=args.structure_mode,
    )

    try:
        run = build_web_structure(config)
        root = write_structure_catalog(run, config)
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Discovered {len(run.entries)} structure entries into {root}")
    if run.issues:
        print(f"Issues: {len(run.issues)}")
    print(f"Structure: {root / '_catalog' / 'structure.yaml'}")
    return 0


def _mirror_config_from_args(args: argparse.Namespace) -> MirrorConfig:
    save_asset_kinds = frozenset(kind.strip() for kind in args.save_assets.split(",") if kind.strip())
    return MirrorConfig(
        source=args.source,
        out_dir=args.out,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        render_js=args.render_js,
        save_asset_kinds=save_asset_kinds,
        include_external=args.include_external,
        respect_robots_txt=not args.ignore_robots,
        scope=args.scope,
        include_url_prefixes=tuple(args.include_url_prefix),
        content_selector=args.content_selector,
        exclude_selector=args.exclude_selector,
        exclude_tags=tuple(args.exclude_tag) if args.exclude_tag else ("script", "style", "noscript"),
        clean_markdown=not args.no_clean_markdown,
        noise_lines=tuple(args.noise_line),
        image_link_mode=args.image_link_mode,
        image_render_mode=args.image_render_mode,
        image_size_mode=args.image_size_mode,
        image_max_width=args.image_max_width,
        anti_bot_mode=args.anti_bot,
        structure_mode=args.structure_mode,
    )


def catalog_command(args: argparse.Namespace) -> int:
    root = args.root
    for name in (
        "summary.yaml",
        "sync.yaml",
        "sync_history.yaml",
        "structure.yaml",
        "pages.yaml",
        "links.yaml",
        "assets.yaml",
        "errors.yaml",
    ):
        path = root / "_catalog" / name
        print(path)
    return 0


def query_command(args: argparse.Namespace) -> int:
    hits = search_files(args.root, args.text, limit=args.limit)
    if not hits:
        print("No hits.")
        return 0
    for index, hit in enumerate(hits, start=1):
        print(f"{index}. score={hit.score} {hit.path}")
        print(f"   {hit.snippet}")
    return 0


def publish_command(args: argparse.Namespace) -> int:
    result = publish_mirror(
        args.root,
        message=args.message,
        dry_run=args.dry_run,
        init=args.init,
        push=args.push,
    )
    print(result.output)
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
