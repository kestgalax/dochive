from __future__ import annotations

import asyncio
import os
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from .html_extract import extract_html_videos, inject_html_videos, promote_markdown_headings
from .markdown_normalizer import normalize_markdown
from .media_utils import extract_markdown_assets, merge_assets
from .models import Asset, MirrorConfig, MirrorIssue, MirrorRun, Page
from .text_utils import repair_mojibake
from .url_utils import canonicalize_url, same_domain


def crawl_web(config: MirrorConfig) -> MirrorRun:
    _configure_crawl4ai_environment(config)
    try:
        import crawl4ai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Web crawling requires Crawl4AI. Install with `pip install .[crawl4ai]` "
            "or pass a local HTML folder to --source."
        ) from exc
    return asyncio.run(_crawl_web_async(config))


def _configure_crawl4ai_environment(config: MirrorConfig) -> None:
    workspace = Path.cwd()
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(workspace / ".crawl4ai-data"))
    local_browsers = workspace / ".playwright-browsers"
    if local_browsers.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(local_browsers))
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


async def _crawl_web_async(config: MirrorConfig) -> list[Page]:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

    _validate_anti_bot_mode(config.anti_bot_mode)

    root_url = canonicalize_url(config.source)
    allowed_prefixes = _allowed_prefixes(root_url, config)
    queue: deque[tuple[str, int, str | None]] = deque([(root_url, 0, None)])
    seen: set[str] = set()
    pages: list[Page] = []
    issues: list[MirrorIssue] = []

    browser_config = BrowserConfig(**_browser_config_kwargs(config))
    run_config = CrawlerRunConfig(**_run_config_kwargs(config))

    async with AsyncWebCrawler(config=browser_config) as crawler:
        if config.crawl4ai_deep:
            pages = await _crawl_web_with_crawl4ai_deep(crawler, run_config, root_url, allowed_prefixes, config)
            return MirrorRun(pages=pages, issues=issues)

        while queue and len(pages) < config.max_pages:
            url, depth, parent_url = queue.popleft()
            url = canonicalize_url(url)
            if url in seen or depth > config.max_depth:
                continue
            seen.add(url)

            try:
                result = await crawler.arun(url=url, config=run_config)
            except Exception as exc:
                issues.append(
                    MirrorIssue(
                        kind="fetch_exception",
                        message=str(exc),
                        url=url,
                        severity="error",
                    )
                )
                continue
            if not getattr(result, "success", False):
                issues.append(
                    MirrorIssue(
                        kind="fetch_failed",
                        message=str(getattr(result, "error_message", "") or "Crawl4AI returned success=false."),
                        url=url,
                        severity="error",
                    )
                )
                continue

            page = _page_from_crawl_result(result, url, depth, parent_url, root_url, allowed_prefixes, config)
            for target in page.links_internal:
                if target not in seen and depth + 1 <= config.max_depth:
                    queue.append((target, depth + 1, url))
            pages.append(page)

    return MirrorRun(pages=pages, issues=issues)


def _browser_config_kwargs(config: MirrorConfig) -> dict[str, object]:
    kwargs: dict[str, object] = {"headless": True}
    if config.anti_bot_mode == "basic":
        kwargs["user_agent_mode"] = "random"
    return kwargs


def _run_config_kwargs(config: MirrorConfig) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "css_selector": config.content_selector,
        "excluded_selector": config.exclude_selector,
        "excluded_tags": list(config.exclude_tags),
        "remove_forms": True,
        "check_robots_txt": False,
    }
    if config.anti_bot_mode == "basic":
        kwargs.update(
            simulate_user=True,
            override_navigator=True,
            magic=True,
        )
    if config.crawl4ai_deep:
        kwargs["deep_crawl_strategy"] = _crawl4ai_deep_strategy(config)
    return kwargs


def _crawl4ai_deep_strategy(config: MirrorConfig):
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.deep_crawling.filters import ContentTypeFilter, FilterChain, URLPatternFilter

    root_url = canonicalize_url(config.source)
    allowed_prefixes = _allowed_prefixes(root_url, config)
    filters = [ContentTypeFilter(allowed_types=["text/html"])]
    if config.scope != "domain" and allowed_prefixes:
        filters.insert(0, URLPatternFilter(patterns=[f"{prefix}*" for prefix in allowed_prefixes]))

    return BFSDeepCrawlStrategy(
        max_depth=config.max_depth,
        max_pages=config.max_pages,
        include_external=config.include_external,
        filter_chain=FilterChain(filters),
    )


async def _crawl_web_with_crawl4ai_deep(
    crawler,
    run_config,
    root_url: str,
    allowed_prefixes: tuple[str, ...],
    config: MirrorConfig,
) -> list[Page]:
    results = await crawler.arun(url=root_url, config=run_config)
    if not isinstance(results, list):
        results = [results]

    pages: list[Page] = []
    seen: set[str] = set()
    for result in results:
        if not getattr(result, "success", False):
            continue
        metadata = getattr(result, "metadata", {}) or {}
        url = canonicalize_url(getattr(result, "url", root_url))
        if url in seen:
            continue
        seen.add(url)
        depth = int(metadata.get("depth", 0) or 0)
        parent_url = metadata.get("parent_url") or metadata.get("parent")
        if parent_url:
            parent_url = canonicalize_url(str(parent_url))
        pages.append(_page_from_crawl_result(result, url, depth, parent_url, root_url, allowed_prefixes, config))
    return pages


def _page_from_crawl_result(
    result,
    url: str,
    depth: int,
    parent_url: str | None,
    root_url: str,
    allowed_prefixes: tuple[str, ...],
    config: MirrorConfig,
) -> Page:
    metadata = getattr(result, "metadata", {}) or {}
    markdown_obj = getattr(result, "markdown", "")
    markdown = getattr(markdown_obj, "raw_markdown", None) or str(markdown_obj or "")
    html = getattr(result, "html", None) or getattr(result, "cleaned_html", "") or ""
    if html:
        markdown = promote_markdown_headings(markdown, html)
        markdown = inject_html_videos(markdown, html, url)
    markdown = normalize_markdown(
        markdown,
        clean=config.clean_markdown,
        extra_noise_lines=config.noise_lines,
    )
    links = getattr(result, "links", {}) or {}
    media = getattr(result, "media", {}) or {}

    internal = []
    external = []
    for item in links.get("internal", []):
        href = item.get("href") if isinstance(item, dict) else None
        if not href:
            continue
        target = canonicalize_url(href, url)
        if _is_allowed_url(target, root_url, allowed_prefixes, config):
            internal.append(target)
        else:
            external.append(target)
    for item in links.get("external", []):
        href = item.get("href") if isinstance(item, dict) else None
        if href:
            external.append(canonicalize_url(href, url))

    assets: list[Asset] = []
    for kind, items in media.items():
        asset_kind = "videos" if kind == "video" else kind
        for item in items:
            if isinstance(item, dict):
                src = item.get("src") or item.get("href")
                if src:
                    assets.append(
                        Asset(
                            source=canonicalize_url(src, url),
                            kind=asset_kind,
                            alt=repair_mojibake(item.get("alt", "")),
                        )
                    )
    if html:
        for sources in extract_html_videos(html, url):
            for source in sources:
                assets.append(Asset(source=canonicalize_url(source, url), kind="videos"))

    markdown_assets = extract_markdown_assets(markdown, url)
    assets = merge_assets(assets, markdown_assets)

    return Page(
        source_url=url,
        canonical_url=canonicalize_url(getattr(result, "url", url)),
        title=repair_mojibake(metadata.get("title", "")),
        description=repair_mojibake(metadata.get("description", "")),
        markdown=markdown,
        depth=depth,
        parent_url=parent_url,
        links_internal=_unique(internal),
        links_external=_unique(external),
        assets=assets,
        status_code=getattr(result, "status_code", 200) or 200,
    )


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


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _allowed_prefixes(root_url: str, config: MirrorConfig) -> tuple[str, ...]:
    prefixes = tuple(canonicalize_url(prefix) for prefix in config.include_url_prefixes)
    if config.scope == "domain":
        return prefixes

    parsed = urlparse(root_url)
    path = parsed.path or "/"
    if "/" in path.rstrip("/"):
        directory = path.rsplit("/", 1)[0].rstrip("/") + "/"
    else:
        directory = "/"
    subtree = parsed._replace(path=directory, params="", query="", fragment="").geturl()
    return (subtree, *prefixes)


def _is_allowed_url(target: str, root_url: str, allowed_prefixes: tuple[str, ...], config: MirrorConfig) -> bool:
    if not same_domain(target, root_url):
        return config.include_external
    if config.scope == "domain":
        return True
    return any(target.startswith(prefix) for prefix in allowed_prefixes)
