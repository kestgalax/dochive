from __future__ import annotations

import asyncio
import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from .auth import request_headers, validate_auth_config
from .confluence import confluence_body_html, confluence_links_and_assets, confluence_markdown
from .html_extract import (
    extract_html_anchor_headings,
    extract_html_videos,
    inject_html_comments,
    extract_html_document_title,
    inject_html_tables,
    inject_html_videos,
    promote_markdown_headings,
)
from .madcap_toc import discover_madcap_structure
from .markdown_normalizer import normalize_markdown
from .media_utils import extract_markdown_assets, merge_assets
from .models import Asset, MirrorConfig, MirrorIssue, MirrorRun, Page, StructureEntry, StructureRun
from .text_utils import repair_mojibake
from .url_utils import (
    HTML_SUFFIXES,
    canonicalize_confluence_url,
    canonicalize_url,
    canonicalize_with_language_prefix,
    extract_tocpath,
    same_domain,
)

MARKDOWN_BREADCRUMB_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|([^>\n]+)")


@dataclass
class NavigationEntry:
    canonical_url: str
    fetch_url: str
    depth: int
    order: int
    discovered_from_url: str | None = None
    nav_parent_url: str | None = None
    nav_path: tuple[str, ...] = ()
    placeholder: bool = False


def crawl_web(config: MirrorConfig) -> MirrorRun:
    _configure_crawl4ai_environment(config)
    _validate_structure_mode(config.structure_mode)
    _validate_source_type(config.source_type)
    _validate_auth_config(config)
    try:
        import crawl4ai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Web crawling requires Crawl4AI. Install with `pip install .[crawl4ai]` "
            "or pass a local HTML folder to --source."
        ) from exc
    return asyncio.run(_crawl_web_async(config))


def build_web_structure(config: MirrorConfig) -> StructureRun:
    _configure_crawl4ai_environment(config)
    _validate_structure_mode(config.structure_mode)
    _validate_source_type(config.source_type)
    _validate_auth_config(config)
    if _uses_madcap_structure(config):
        run = discover_madcap_structure(config)
        if run.entries or config.structure_mode == "toc":
            if config.structure_mode == "toc" and run.issues:
                raise RuntimeError(run.issues[0].message)
            return run

    try:
        import crawl4ai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Web structure discovery requires Crawl4AI. Install with `pip install .[crawl4ai]` "
            "or use `dochive mirror` with a local HTML folder."
        ) from exc
    return asyncio.run(_build_web_structure_async(config))


def _configure_crawl4ai_environment(config: MirrorConfig) -> None:
    workspace = Path.cwd()
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(workspace / ".crawl4ai-data"))
    local_browsers = workspace / ".playwright-browsers"
    if local_browsers.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(local_browsers))
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


async def _crawl_web_async(config: MirrorConfig) -> MirrorRun:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

    _validate_anti_bot_mode(config.anti_bot_mode)
    _validate_structure_mode(config.structure_mode)

    root_url = _canonicalize_source_url(config.source, config)
    allowed_prefixes = _allowed_prefixes(root_url, config)
    root_fetch_url = config.source
    root_nav_path = extract_tocpath(config.source)
    issues: list[MirrorIssue] = []

    browser_config_kwargs = _browser_config_kwargs(config)
    run_config_kwargs = _run_config_kwargs(config)

    browser_config = BrowserConfig(**browser_config_kwargs)
    run_config = CrawlerRunConfig(
        css_selector=_content_selector(config),
        excluded_selector=config.exclude_selector,
        excluded_tags=list(config.exclude_tags),
        remove_forms=True,
        check_robots_txt=False,
        **run_config_kwargs,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        if _uses_madcap_structure(config):
            structure_run = discover_madcap_structure(config)
            if structure_run.entries:
                pages, page_issues = await _fetch_pages_from_structure_entries(
                    crawler,
                    run_config,
                    config,
                    structure_run.entries,
                    root_url=root_url,
                    allowed_prefixes=allowed_prefixes,
                )
                issues.extend(structure_run.issues)
                issues.extend(page_issues)
                return MirrorRun(pages=pages, issues=issues)
            if config.structure_mode == "toc":
                message = structure_run.issues[0].message if structure_run.issues else "MadCap TOC discovery failed."
                raise RuntimeError(message)
            issues.extend(structure_run.issues)

        nav_index, nav_issues = await _build_navigation_index(
            crawler,
            run_config,
            config,
            root_url=root_url,
            root_fetch_url=root_fetch_url,
            root_nav_path=root_nav_path,
            allowed_prefixes=allowed_prefixes,
        )
        issues.extend(nav_issues)
        pages, page_issues = await _fetch_pages_from_navigation_index(
            crawler,
            run_config,
            config,
            nav_index,
            root_url=root_url,
            allowed_prefixes=allowed_prefixes,
        )
        issues.extend(page_issues)

    return MirrorRun(pages=pages, issues=issues)


async def _build_web_structure_async(config: MirrorConfig) -> StructureRun:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

    _validate_anti_bot_mode(config.anti_bot_mode)
    _validate_structure_mode(config.structure_mode)

    root_fetch_url = config.source if config.source_type == "confluence" else _structure_root_fetch_url(config.source)
    root_url = _canonicalize_source_url(root_fetch_url, config)
    allowed_prefixes = _allowed_prefixes(root_url, config)
    root_nav_path = extract_tocpath(root_fetch_url)

    browser_config_kwargs = _browser_config_kwargs(config)
    run_config_kwargs = _run_config_kwargs(config)

    browser_config = BrowserConfig(**browser_config_kwargs)
    run_config = CrawlerRunConfig(
        css_selector=_content_selector(config),
        excluded_selector=config.exclude_selector,
        excluded_tags=list(config.exclude_tags),
        remove_forms=True,
        check_robots_txt=False,
        **run_config_kwargs,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        nav_index, issues = await _build_navigation_index(
            crawler,
            run_config,
            config,
            root_url=root_url,
            root_fetch_url=root_fetch_url,
            root_nav_path=root_nav_path,
            allowed_prefixes=allowed_prefixes,
        )

    return StructureRun(entries=_navigation_entries_to_structure(nav_index, root_url=root_url), issues=issues)


def _structure_root_fetch_url(source: str) -> str:
    parsed = urlparse(source)
    parts = [part for part in parsed.path.split("/") if part]
    lowered = [part.lower() for part in parts]
    if "content" not in lowered or _is_main_page_url(source):
        return source
    content_index = lowered.index("content")
    root_parts = parts[: content_index + 1] + ["main_page.htm"]
    root_path = "/" + "/".join(root_parts)
    return parsed._replace(path=root_path, params="", query="", fragment="").geturl()


def _browser_config_kwargs(config: MirrorConfig) -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True}
    headers = request_headers(config)
    if headers:
        kwargs["headers"] = headers
    if config.anti_bot_mode == "basic":
        kwargs["user_agent_mode"] = "random"
    return kwargs


def _run_config_kwargs(config: MirrorConfig) -> dict[str, object]:
    if config.anti_bot_mode != "basic":
        return {}
    return {
        "simulate_user": True,
        "override_navigator": True,
        "magic": True,
    }


def _content_selector(config: MirrorConfig) -> str | None:
    if config.content_selector:
        return config.content_selector
    if config.source_type == "confluence":
        return "#main-content .wiki-content, .wiki-content"
    return None


async def _build_navigation_index(
    crawler: object,
    run_config: object,
    config: MirrorConfig,
    *,
    root_url: str,
    root_fetch_url: str,
    root_nav_path: tuple[str, ...],
    allowed_prefixes: tuple[str, ...],
) -> tuple[dict[str, NavigationEntry], list[MirrorIssue]]:
    entries: dict[str, NavigationEntry] = {
        root_url: NavigationEntry(
            canonical_url=root_url,
            fetch_url=root_fetch_url,
            depth=0,
            order=1,
            nav_path=root_nav_path,
        )
    }
    fetch_url_by_canonical: dict[str, str] = {root_url: root_fetch_url}
    nav_path_by_canonical: dict[str, tuple[str, ...]] = {root_url: root_nav_path} if root_nav_path else {}
    nav_parent_by_canonical: dict[str, str] = {}
    queue: deque[str] = deque([root_url])
    seen: set[str] = set()
    issues: list[MirrorIssue] = []

    while queue:
        url = queue.popleft()
        entry = entries.get(url)
        if not entry or url in seen or entry.depth > config.max_depth:
            continue
        seen.add(url)

        result, issue = await _fetch_crawl_result(crawler, run_config, entry.fetch_url, "navigation")
        if issue:
            issues.append(issue)
            continue

        metadata = getattr(result, "metadata", {}) or {}
        title = repair_mojibake(metadata.get("title", ""))
        links = getattr(result, "links", {}) or {}
        internal_links = list(links.get("internal", [])) if isinstance(links, dict) else []
        internal_links.sort(key=lambda item: 0 if _link_tocpath(item, entry.fetch_url) else 1)
        for item in internal_links:
            href = item.get("href") if isinstance(item, dict) else None
            if not href:
                continue
            if _is_service_or_placeholder_href(href):
                continue
            link_text = repair_mojibake(str(item.get("text") or item.get("title") or "")).strip()
            target_fetch_url = urljoin(entry.fetch_url, href)
            target = _canonicalize_crawl_url(target_fetch_url, root_url, config)
            if target == url:
                continue
            if target == root_url and url != root_url:
                continue
            if _is_service_or_placeholder_url(target):
                continue
            if not _is_html_page_candidate(target):
                continue
            if not _is_allowed_url(target, root_url, allowed_prefixes, config):
                _remember_placeholder_entry(
                    entries,
                    target=target,
                    target_fetch_url=target_fetch_url,
                    target_nav_path=extract_tocpath(target_fetch_url),
                    link_text=link_text,
                    current_entry=entry,
                    root_url=root_url,
                )
                continue

            target_nav_path = extract_tocpath(target_fetch_url)
            if _is_synthetic_root_link(entry, root_url):
                target_nav_path = _synthetic_root_nav_path(target_nav_path, link_text, target)
            nav_path, nav_parent_url = _navigation_hint(
                target,
                target_nav_path=target_nav_path,
                link_text=link_text,
                current_url=url,
                current_title=title,
            )
            depth = entry.depth + 1
            fetched_entry_count = len([item for item in entries.values() if not item.placeholder])
            if target not in entries and (depth > config.max_depth or fetched_entry_count >= config.max_pages):
                _remember_placeholder_entry(
                    entries,
                    target=target,
                    target_fetch_url=target_fetch_url,
                    target_nav_path=target_nav_path,
                    link_text=link_text,
                    current_entry=entry,
                    root_url=root_url,
                )
                continue
            if target not in entries:
                entries[target] = NavigationEntry(
                    canonical_url=target,
                    fetch_url=target_fetch_url,
                    depth=depth,
                    order=len(entries) + 1,
                    discovered_from_url=url,
                    nav_parent_url=None if _is_synthetic_root_link(entry, root_url) else url if not target_nav_path else None,
                    nav_path=_plain_link_nav_path(entry.nav_path, link_text, target) if not target_nav_path else (),
                )

            _remember_navigation_hint(
                target,
                target_fetch_url=target_fetch_url,
                target_nav_path=target_nav_path,
                link_text=link_text,
                current_url=url,
                current_title=title,
                fetch_url_by_canonical=fetch_url_by_canonical,
                nav_path_by_canonical=nav_path_by_canonical,
                nav_parent_by_canonical=nav_parent_by_canonical,
                page_by_canonical={},
            )
            _sync_navigation_entry(
                entries[target],
                fetch_url_by_canonical=fetch_url_by_canonical,
                nav_path_by_canonical=nav_path_by_canonical,
                nav_parent_by_canonical=nav_parent_by_canonical,
            )
            if nav_parent_url == url:
                entries[target].depth = entry.depth + 1
            if target not in seen and entries[target].depth <= config.max_depth:
                queue.append(target)

    return entries, issues


async def _fetch_pages_from_navigation_index(
    crawler: object,
    run_config: object,
    config: MirrorConfig,
    nav_index: dict[str, NavigationEntry],
    *,
    root_url: str,
    allowed_prefixes: tuple[str, ...],
) -> tuple[list[Page], list[MirrorIssue]]:
    pages: list[Page] = []
    issues: list[MirrorIssue] = []

    for entry in sorted(nav_index.values(), key=lambda item: item.order):
        if entry.depth > config.max_depth:
            continue
        fetched_pages = len([page for page in pages if not page.placeholder])
        if not entry.placeholder and fetched_pages >= config.max_pages:
            issues.append(MirrorIssue(
                kind="max_pages_reached",
                message=f"Stopped after {config.max_pages} pages",
                severity="info",
            ))
            break
        if entry.placeholder:
            title = entry.nav_path[-1] if entry.nav_path else entry.canonical_url.rsplit("/", 1)[-1]
            pages.append(
                Page(
                    source_url=entry.fetch_url,
                    canonical_url=entry.canonical_url,
                    title=title,
                    markdown=_placeholder_markdown(title, entry.fetch_url),
                    depth=entry.depth,
                    parent_url=entry.discovered_from_url,
                    nav_parent_url=entry.nav_parent_url,
                    nav_path=entry.nav_path,
                    placeholder=True,
                )
            )
            continue

        result, issue = await _fetch_crawl_result(crawler, run_config, entry.fetch_url, "content")
        if issue:
            issues.append(issue)
            continue

        metadata = getattr(result, "metadata", {}) or {}
        title = repair_mojibake(metadata.get("title", ""))
        markdown_obj = getattr(result, "markdown", "")
        markdown = getattr(markdown_obj, "raw_markdown", None) or str(markdown_obj or "")
        html = getattr(result, "html", None) or getattr(result, "cleaned_html", "") or ""
        links = getattr(result, "links", {}) or {}
        media = getattr(result, "media", {}) or {}
        if config.source_type == "confluence" and html:
            html = confluence_body_html(html)
            markdown = confluence_markdown(html, entry.fetch_url)
            links, media = confluence_links_and_assets(html, entry.fetch_url)
        if html:
            document_title = extract_html_document_title(html)
            if document_title:
                title = document_title
            markdown = promote_markdown_headings(markdown, html)
            markdown = inject_html_videos(markdown, html, entry.fetch_url)
            if config.source_type != "confluence":
                markdown = inject_html_tables(markdown, html, entry.fetch_url)
            markdown = inject_html_comments(markdown, html)
        anchor_headings = extract_html_anchor_headings(html) if html else {}
        markdown = normalize_markdown(
            markdown,
            clean=config.clean_markdown,
            extra_noise_lines=config.noise_lines,
            anchor_headings=anchor_headings,
        )
        internal, external = _extract_page_links(links, entry.fetch_url, root_url, allowed_prefixes, config)
        assets = _extract_page_assets(media, html, markdown, entry.fetch_url)

        pages.append(
            Page(
                source_url=entry.fetch_url,
                canonical_url=entry.canonical_url,
                title=title,
                description=repair_mojibake(metadata.get("description", "")),
                markdown=markdown,
                depth=entry.depth,
                parent_url=entry.discovered_from_url,
                nav_parent_url=entry.nav_parent_url,
                nav_path=entry.nav_path or _extract_markdown_breadcrumb_path(markdown),
                links_internal=internal,
                links_external=external,
                anchor_headings=anchor_headings,
                assets=assets,
                status_code=getattr(result, "status_code", 200) or 200,
            )
        )
    return pages, issues


async def _fetch_pages_from_structure_entries(
    crawler: object,
    run_config: object,
    config: MirrorConfig,
    entries: list[StructureEntry],
    *,
    root_url: str,
    allowed_prefixes: tuple[str, ...],
) -> tuple[list[Page], list[MirrorIssue]]:
    pages: list[Page] = []
    issues: list[MirrorIssue] = []
    fetched_pages = 0

    for entry in sorted(entries, key=lambda item: item.order):
        if fetched_pages >= config.max_pages:
            pages.append(_placeholder_page_from_structure_entry(entry))
            continue

        result, issue = await _fetch_crawl_result(crawler, run_config, entry.fetch_url, "content")
        if issue:
            issues.append(issue)
            pages.append(_placeholder_page_from_structure_entry(entry))
            continue

        fetched_pages += 1
        metadata = getattr(result, "metadata", {}) or {}
        title = entry.title or repair_mojibake(metadata.get("title", ""))
        markdown_obj = getattr(result, "markdown", "")
        markdown = getattr(markdown_obj, "raw_markdown", None) or str(markdown_obj or "")
        html = getattr(result, "html", None) or getattr(result, "cleaned_html", "") or ""
        links = getattr(result, "links", {}) or {}
        media = getattr(result, "media", {}) or {}
        if config.source_type == "confluence" and html:
            html = confluence_body_html(html)
            markdown = confluence_markdown(html, entry.fetch_url)
            links, media = confluence_links_and_assets(html, entry.fetch_url)
        if html:
            document_title = extract_html_document_title(html)
            if document_title:
                title = document_title
            markdown = promote_markdown_headings(markdown, html)
            markdown = inject_html_videos(markdown, html, entry.fetch_url)
            if config.source_type != "confluence":
                markdown = inject_html_tables(markdown, html, entry.fetch_url)
            markdown = inject_html_comments(markdown, html)
        anchor_headings = extract_html_anchor_headings(html) if html else {}
        markdown = normalize_markdown(
            markdown,
            clean=config.clean_markdown,
            extra_noise_lines=config.noise_lines,
            anchor_headings=anchor_headings,
        )
        internal, external = _extract_page_links(links, entry.fetch_url, root_url, allowed_prefixes, config)
        assets = _extract_page_assets(media, html, markdown, entry.fetch_url)

        pages.append(
            Page(
                source_url=entry.fetch_url,
                canonical_url=entry.canonical_url,
                title=title,
                description=repair_mojibake(metadata.get("description", "")),
                markdown=markdown,
                depth=entry.depth,
                nav_parent_url=entry.nav_parent_url,
                nav_path=entry.nav_path,
                links_internal=internal,
                links_external=external,
                anchor_headings=anchor_headings,
                assets=assets,
                status_code=getattr(result, "status_code", 200) or 200,
            )
        )
    return pages, issues


def _navigation_entries_to_structure(
    nav_index: dict[str, NavigationEntry],
    *,
    root_url: str | None = None,
) -> list[StructureEntry]:
    synthetic_root = root_url if root_url and _is_main_page_url(root_url) else None
    return [
        StructureEntry(
            canonical_url=entry.canonical_url,
            fetch_url=entry.fetch_url,
            title=_structure_title(entry),
            depth=entry.depth,
            order=entry.order,
            nav_parent_url=None if entry.nav_parent_url == synthetic_root else entry.nav_parent_url,
            nav_path=entry.nav_path,
            placeholder=True,
        )
        for entry in sorted(nav_index.values(), key=lambda item: item.order)
        if not _is_synthetic_structure_root(entry, root_url)
    ]


def _structure_title(entry: NavigationEntry) -> str:
    if entry.nav_path:
        return entry.nav_path[-1]
    stem = Path(urlparse(entry.canonical_url).path).stem
    return stem.replace("-", " ").replace("_", " ").title() or entry.canonical_url.rsplit("/", 1)[-1]


async def _fetch_crawl_result(
    crawler: object,
    run_config: object,
    fetch_url: str,
    phase: str,
) -> tuple[object | None, MirrorIssue | None]:
    try:
        result = await crawler.arun(url=fetch_url, config=run_config)
    except Exception as exc:
        return None, MirrorIssue(
            kind=f"{phase}_fetch_exception",
            message=str(exc),
            url=fetch_url,
            severity="error",
        )
    if not getattr(result, "success", False):
        return None, MirrorIssue(
            kind=f"{phase}_fetch_failed",
            message=str(getattr(result, "error_message", "") or "Crawl4AI returned success=false."),
            url=fetch_url,
            severity="error",
        )
    return result, None


def _remember_navigation_hint(
    target: str,
    *,
    target_fetch_url: str,
    target_nav_path: tuple[str, ...],
    link_text: str,
    current_url: str,
    current_title: str,
    fetch_url_by_canonical: dict[str, str],
    nav_path_by_canonical: dict[str, tuple[str, ...]],
    nav_parent_by_canonical: dict[str, str],
    page_by_canonical: dict[str, Page],
) -> None:
    if not target_nav_path:
        if current_url and link_text:
            nav_parent_by_canonical.setdefault(target, current_url)
            if target not in nav_path_by_canonical:
                parent_path = nav_path_by_canonical.get(current_url) or next(
                    (
                        page.nav_path
                        for page in page_by_canonical.values()
                        if page.canonical_url == current_url and page.nav_path
                    ),
                    (),
                )
                if parent_path:
                    nav_path_by_canonical[target] = _plain_link_nav_path(parent_path, link_text, target)
        fetch_url_by_canonical.setdefault(target, target_fetch_url)
        return

    nav_path, nav_parent_url = _navigation_hint(
        target,
        target_nav_path=target_nav_path,
        link_text=link_text,
        current_url=current_url,
        current_title=current_title,
    )

    pinned_section_landing = _is_pinned_section_landing_path(target, nav_path_by_canonical.get(target))
    should_update_nav = _prefer_nav_path(nav_path, nav_path_by_canonical.get(target))
    if pinned_section_landing:
        should_update_nav = False
    if should_update_nav:
        nav_path_by_canonical[target] = nav_path
        if page := page_by_canonical.get(target):
            page.nav_path = nav_path

    should_update_fetch_url = should_update_nav or not extract_tocpath(fetch_url_by_canonical.get(target, ""))
    if should_update_fetch_url:
        fetch_url_by_canonical[target] = target_fetch_url
        if page := page_by_canonical.get(target):
            page.source_url = target_fetch_url

    if nav_parent_url and not pinned_section_landing and (target not in nav_parent_by_canonical or should_update_nav):
        nav_parent_by_canonical[target] = nav_parent_url
        if page := page_by_canonical.get(target):
            page.nav_parent_url = nav_parent_url


def _remember_placeholder_entry(
    entries: dict[str, NavigationEntry],
    *,
    target: str,
    target_fetch_url: str,
    target_nav_path: tuple[str, ...],
    link_text: str,
    current_entry: NavigationEntry,
    root_url: str,
) -> None:
    if target in entries or not _is_placeholder_candidate(target, root_url):
        return
    nav_path = target_nav_path
    if not nav_path:
        title = _placeholder_title(link_text, target)
        nav_path = _plain_link_nav_path(current_entry.nav_path, link_text, target) or (_url_section_label(target), title)
    else:
        title = nav_path[-1]
    entries[target] = NavigationEntry(
        canonical_url=target,
        fetch_url=target_fetch_url,
        depth=current_entry.depth + 1,
        order=len(entries) + 1,
        discovered_from_url=current_entry.canonical_url,
        nav_parent_url=_placeholder_parent_url(nav_path, target_nav_path, current_entry),
        nav_path=nav_path,
        placeholder=True,
    )


def _plain_link_nav_path(parent_nav_path: tuple[str, ...], link_text: str, target: str) -> tuple[str, ...]:
    if not parent_nav_path:
        return ()
    title = _placeholder_title(link_text, target)
    return (*parent_nav_path, title)


def _is_synthetic_root_link(entry: NavigationEntry, root_url: str) -> bool:
    return entry.canonical_url == root_url and _is_main_page_url(root_url) and not entry.nav_path


def _synthetic_root_nav_path(
    target_nav_path: tuple[str, ...],
    link_text: str,
    target: str,
) -> tuple[str, ...]:
    if target_nav_path and not _is_section_landing_page(target):
        return target_nav_path
    if target_nav_path:
        return (target_nav_path[-1],)
    return (_placeholder_title(link_text, target),)


def _is_pinned_section_landing_path(target: str, current: tuple[str, ...] | None) -> bool:
    return bool(current and len(current) == 1 and _is_section_landing_page(target))


def _is_section_landing_page(target: str) -> bool:
    parts = [part for part in urlparse(target).path.strip("/").split("/") if part]
    lowered = [part.lower() for part in parts]
    if "content" in lowered:
        after_content = parts[lowered.index("content") + 1 :]
    else:
        after_content = parts
    if len(after_content) == 1:
        return True
    if len(after_content) < 2:
        return False
    parent = Path(after_content[-2]).stem.casefold()
    stem = Path(after_content[-1]).stem.casefold()
    return stem == parent or stem.endswith("_toc")


def _is_synthetic_structure_root(entry: NavigationEntry, root_url: str | None) -> bool:
    return bool(root_url and entry.canonical_url == root_url and _is_main_page_url(root_url) and not entry.nav_path)


def _is_main_page_url(url: str) -> bool:
    return Path(urlparse(url).path).name.lower() in {"main_page.htm", "main_page.html", "main_page.xhtml"}


def _is_html_page_candidate(url: str) -> bool:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix:
        return suffix in HTML_SUFFIXES
    return True


def _is_placeholder_candidate(target: str, root_url: str) -> bool:
    if not same_domain(target, root_url):
        return False
    parsed = urlparse(target)
    path = parsed.path.lower()
    if path.endswith("/main_page.htm") or path.endswith("/main_page.html"):
        return False
    return path.endswith((".htm", ".html", ".xhtml"))


def _placeholder_title(link_text: str, target: str) -> str:
    clean = re.sub(r"\s+", " ", link_text).strip()
    if clean and not re.fullmatch(r"подробнее|подробное описание", clean, re.IGNORECASE):
        return clean
    stem = Path(urlparse(target).path).stem
    return stem.replace("-", " ").replace("_", " ").title() or target.rsplit("/", 1)[-1]


def _url_section_label(target: str) -> str:
    parts = [part for part in urlparse(target).path.strip("/").split("/") if part]
    if len(parts) >= 2:
        return parts[-2].replace("-", " ").replace("_", " ").title()
    return "Раздел"


def _placeholder_parent_url(
    nav_path: tuple[str, ...],
    target_nav_path: tuple[str, ...],
    current_entry: NavigationEntry,
) -> str | None:
    if not target_nav_path:
        return None
    if len(nav_path) > 1 and nav_path[:-1] == current_entry.nav_path:
        return current_entry.canonical_url
    return None


def _placeholder_markdown(title: str, source_url: str) -> str:
    return (
        f"# {title}\n\n"
        "Раздел ожидает отдельного зеркалирования.\n\n"
        f"Источник: {source_url}\n"
    )


def _placeholder_page_from_structure_entry(entry: StructureEntry) -> Page:
    return Page(
        source_url=entry.fetch_url,
        canonical_url=entry.canonical_url,
        title=entry.title,
        markdown=_placeholder_markdown(entry.title, entry.fetch_url),
        depth=entry.depth,
        nav_parent_url=entry.nav_parent_url,
        nav_path=entry.nav_path,
        placeholder=True,
    )


def _navigation_hint(
    target: str,
    *,
    target_nav_path: tuple[str, ...],
    link_text: str,
    current_url: str,
    current_title: str,
) -> tuple[tuple[str, ...], str | None]:
    if not target_nav_path:
        return (), None
    nav_path = target_nav_path
    nav_parent_url: str | None = None
    if target != current_url:
        if _nav_path_points_to_current_page(target_nav_path, current_title):
            nav_parent_url = current_url
            if link_text:
                nav_path = (*target_nav_path, link_text)
        elif _nav_path_points_to_current_page(target_nav_path[:-1], current_title):
            nav_parent_url = current_url
    return nav_path, nav_parent_url


def _link_tocpath(item: object, base_url: str) -> tuple[str, ...]:
    href = item.get("href") if isinstance(item, dict) else None
    return extract_tocpath(urljoin(base_url, href)) if href else ()


def _sync_navigation_entry(
    entry: NavigationEntry,
    *,
    fetch_url_by_canonical: dict[str, str],
    nav_path_by_canonical: dict[str, tuple[str, ...]],
    nav_parent_by_canonical: dict[str, str],
) -> None:
    entry.fetch_url = fetch_url_by_canonical.get(entry.canonical_url, entry.fetch_url)
    entry.nav_path = nav_path_by_canonical.get(entry.canonical_url, entry.nav_path)
    entry.nav_parent_url = nav_parent_by_canonical.get(entry.canonical_url, entry.nav_parent_url)


def _prefer_nav_path(candidate: tuple[str, ...], current: tuple[str, ...] | None) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    return len(candidate) > len(current)


def _extract_page_links(
    links: object,
    fetch_url: str,
    root_url: str,
    allowed_prefixes: tuple[str, ...],
    config: MirrorConfig,
) -> tuple[list[str], list[str]]:
    internal: list[str] = []
    external: list[str] = []
    link_groups = links if isinstance(links, dict) else {}
    for item in link_groups.get("internal", []):
        href = item.get("href") if isinstance(item, dict) else None
        if not href:
            continue
        if _is_service_or_placeholder_href(href):
            continue
        target = _canonicalize_crawl_url(urljoin(fetch_url, href), root_url, config)
        if _is_service_or_placeholder_url(target):
            continue
        if _is_allowed_url(target, root_url, allowed_prefixes, config):
            internal.append(target)
        else:
            external.append(target)
    for item in link_groups.get("external", []):
        href = item.get("href") if isinstance(item, dict) else None
        if href:
            external.append(canonicalize_url(href, fetch_url))
    return _unique(internal), _unique(external)


def _extract_page_assets(
    media: object,
    html: str,
    markdown: str,
    fetch_url: str,
) -> list[Asset]:
    assets: list[Asset] = []
    media_groups = media if isinstance(media, dict) else {}
    for kind, items in media_groups.items():
        asset_kind = "videos" if kind == "video" else kind
        for item in items:
            if isinstance(item, dict):
                src = item.get("src") or item.get("href")
                if src:
                    assets.append(
                        Asset(
                            source=canonicalize_url(src, fetch_url),
                            kind=asset_kind,
                            alt=repair_mojibake(item.get("alt", "")),
                        )
                    )
    if html:
        for sources in extract_html_videos(html, fetch_url):
            for source in sources:
                assets.append(Asset(source=canonicalize_url(source, fetch_url), kind="videos"))

    return merge_assets(assets, extract_markdown_assets(markdown, fetch_url))


def _extract_markdown_breadcrumb_path(markdown: str) -> tuple[str, ...]:
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if " > " not in stripped or stripped.startswith("#"):
            return ()
        parts: list[str] = []
        for raw_part in stripped.split(">"):
            part = raw_part.strip()
            if not part:
                continue
            match = MARKDOWN_BREADCRUMB_RE.fullmatch(part)
            text = match.group(1) if match and match.group(1) else part
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text).strip()
            if text:
                parts.append(repair_mojibake(text))
        return tuple(parts)
    return ()


def _nav_path_points_to_current_page(nav_path: tuple[str, ...], page_title: str) -> bool:
    if not nav_path or not page_title:
        return False
    return _navigation_label_key(nav_path[-1]) == _navigation_label_key(page_title)


def _navigation_label_key(value: str) -> str:
    value = re.split(r"\s+[\u2013\u2014-]\s+", value, maxsplit=1)[0]
    return re.sub(r"[^0-9a-z\u0430-\u044f\u0451]+", "", value.casefold().replace("\xa0", " "))


def _validate_anti_bot_mode(mode: str) -> None:
    if mode in {"off", "basic"}:
        return
    if mode == "stealth":
        raise RuntimeError(
            "`--anti-bot stealth` is reserved for a future implementation. "
            "Use `--anti-bot basic` for the current default anti-detection profile."
        )
    if mode == "aggressive":
        raise RuntimeError(
            "`--anti-bot aggressive` is reserved for future proxy escalation and fallback fetch support. "
            "Use `--anti-bot basic` until proxies and fallback providers are configured."
        )
    raise RuntimeError(f"Unsupported anti-bot mode: {mode}")


def _validate_structure_mode(mode: str) -> None:
    if mode in {"auto", "toc", "links"}:
        return
    raise RuntimeError(f"Unsupported structure mode: {mode}")


def _validate_source_type(source_type: str) -> None:
    if source_type in {"auto", "generic", "madcap", "wikijs", "confluence"}:
        return
    raise RuntimeError(f"Unsupported source type: {source_type}")


def _validate_auth_config(config: MirrorConfig) -> None:
    validate_auth_config(config)


def _uses_madcap_structure(config: MirrorConfig) -> bool:
    if config.source_type in {"confluence", "generic", "wikijs"}:
        return False
    if config.source_type == "madcap":
        return True
    return config.structure_mode != "links"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _allowed_prefixes(root_url: str, config: MirrorConfig) -> tuple[str, ...]:
    prefixes = tuple(canonicalize_url(prefix) for prefix in config.include_url_prefixes)
    if config.scope == "domain":
        return prefixes

    parsed = urlparse(root_url)
    path = parsed.path or "/"
    suffix = Path(unquote(path)).suffix.lower()
    if path not in {"", "/"} and suffix not in HTML_SUFFIXES:
        subtree_path = path.rstrip("/") + "/"
        subtree = parsed._replace(path=subtree_path, params="", query="", fragment="").geturl()
        return (canonicalize_url(root_url), subtree, *prefixes)
    if "/" in path.rstrip("/"):
        directory = path.rsplit("/", 1)[0].rstrip("/") + "/"
    else:
        directory = "/"
    subtree = parsed._replace(path=directory, params="", query="", fragment="").geturl()
    return (subtree, *prefixes)


def _is_allowed_url(target: str, root_url: str, allowed_prefixes: tuple[str, ...], config: MirrorConfig) -> bool:
    if _is_service_or_placeholder_url(target):
        return False
    if not same_domain(target, root_url):
        return config.include_external
    if config.scope == "domain":
        return True
    return any(target.startswith(prefix) for prefix in allowed_prefixes)


def _canonicalize_source_url(url: str, config: MirrorConfig) -> str:
    if config.source_type == "confluence":
        return canonicalize_confluence_url(url)
    return canonicalize_url(url)


def _canonicalize_crawl_url(url: str, root_url: str, config: MirrorConfig | None = None) -> str:
    if config and config.source_type == "confluence":
        return canonicalize_confluence_url(url, root_url)
    return canonicalize_with_language_prefix(url, root_url)


def _is_service_or_placeholder_href(href: str) -> bool:
    stripped = href.strip()
    if not stripped or stripped in {"#", "...", "./...", "../..."}:
        return True
    parsed = urlparse(stripped)
    if parsed.fragment and not parsed.path and not parsed.netloc:
        return True
    return _is_service_or_placeholder_path(parsed.path)


def _is_service_or_placeholder_url(url: str) -> bool:
    parsed = urlparse(url)
    return _is_service_or_placeholder_path(parsed.path)


def _is_service_or_placeholder_path(path: str) -> bool:
    parts = [unquote(part).strip().casefold() for part in path.split("/") if part.strip()]
    if not parts:
        return False
    if parts[-1] in {"...", "login", "logout", "signin", "sign-in", "auth", "register"}:
        return True
    if len(parts) == 1 and parts[0] in {"t", "tags"}:
        return True
    return any(part in {"_profile", "_settings"} for part in parts)
