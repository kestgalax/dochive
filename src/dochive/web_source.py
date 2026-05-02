from __future__ import annotations

import asyncio
import os
import re
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .html_extract import extract_html_anchor_headings, extract_html_videos, inject_html_videos, promote_markdown_headings
from .markdown_normalizer import normalize_markdown
from .media_utils import extract_markdown_assets, merge_assets
from .models import Asset, MirrorConfig, MirrorIssue, MirrorRun, Page
from .text_utils import repair_mojibake
from .url_utils import canonicalize_url, extract_tocpath, same_domain

MARKDOWN_BREADCRUMB_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|([^>\n]+)")


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
    root_fetch_url = config.source
    root_nav_path = extract_tocpath(config.source)
    queue: deque[tuple[str, int, str | None]] = deque([(root_url, 0, None)])
    fetch_url_by_canonical: dict[str, str] = {root_url: root_fetch_url}
    nav_path_by_canonical: dict[str, tuple[str, ...]] = {root_url: root_nav_path} if root_nav_path else {}
    nav_parent_by_canonical: dict[str, str] = {}
    seen: set[str] = set()
    pages: list[Page] = []
    page_by_canonical: dict[str, Page] = {}
    issues: list[MirrorIssue] = []

    browser_config_kwargs: dict[str, object] = {"headless": True}
    run_config_kwargs: dict[str, object] = {}
    if config.anti_bot_mode == "basic":
        browser_config_kwargs["user_agent_mode"] = "random"
        run_config_kwargs.update(
            simulate_user=True,
            override_navigator=True,
            magic=True,
        )

    browser_config = BrowserConfig(**browser_config_kwargs)
    run_config = CrawlerRunConfig(
        css_selector=config.content_selector,
        excluded_selector=config.exclude_selector,
        excluded_tags=list(config.exclude_tags),
        remove_forms=True,
        check_robots_txt=False,
        **run_config_kwargs,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        while queue and len(pages) < config.max_pages:
            url, depth, parent_url = queue.popleft()
            url = canonicalize_url(url)
            if url in seen or depth > config.max_depth:
                continue
            seen.add(url)
            fetch_url = fetch_url_by_canonical.get(url, url)

            try:
                result = await crawler.arun(url=fetch_url, config=run_config)
            except Exception as exc:
                issues.append(
                    MirrorIssue(
                        kind="fetch_exception",
                        message=str(exc),
                        url=fetch_url,
                        severity="error",
                    )
                )
                continue
            if not getattr(result, "success", False):
                issues.append(
                    MirrorIssue(
                        kind="fetch_failed",
                        message=str(getattr(result, "error_message", "") or "Crawl4AI returned success=false."),
                        url=fetch_url,
                        severity="error",
                    )
                )
                continue

            metadata = getattr(result, "metadata", {}) or {}
            title = repair_mojibake(metadata.get("title", ""))
            markdown_obj = getattr(result, "markdown", "")
            markdown = getattr(markdown_obj, "raw_markdown", None) or str(markdown_obj or "")
            html = getattr(result, "html", None) or getattr(result, "cleaned_html", "") or ""
            if html:
                markdown = promote_markdown_headings(markdown, html)
                markdown = inject_html_videos(markdown, html, fetch_url)
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
                link_text = repair_mojibake(str(item.get("text") or item.get("title") or "")).strip()
                target_fetch_url = urljoin(fetch_url, href)
                target = canonicalize_url(target_fetch_url)
                target_nav_path = extract_tocpath(target_fetch_url)
                if _is_allowed_url(target, root_url, allowed_prefixes, config):
                    internal.append(target)
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
                        page_by_canonical=page_by_canonical,
                    )
                    if target not in seen and depth + 1 <= config.max_depth:
                        queue.append((target, depth + 1, url))
                else:
                    external.append(target)
            for item in links.get("external", []):
                href = item.get("href") if isinstance(item, dict) else None
                if href:
                    external.append(canonicalize_url(href, fetch_url))

            assets: list[Asset] = []
            for kind, items in media.items():
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

            markdown_assets = extract_markdown_assets(markdown, fetch_url)
            assets = merge_assets(assets, markdown_assets)
            result_url = canonicalize_url(getattr(result, "url", url))
            nav_path = nav_path_by_canonical.get(url) or _extract_markdown_breadcrumb_path(markdown)

            page = Page(
                source_url=fetch_url_by_canonical.get(url, fetch_url),
                canonical_url=result_url,
                title=title,
                description=repair_mojibake(metadata.get("description", "")),
                markdown=markdown,
                depth=depth,
                parent_url=parent_url,
                nav_parent_url=nav_parent_by_canonical.get(url),
                nav_path=nav_path,
                links_internal=_unique(internal),
                links_external=_unique(external),
                anchor_headings=extract_html_anchor_headings(html) if html else {},
                assets=assets,
                status_code=getattr(result, "status_code", 200) or 200,
            )
            pages.append(page)
            page_by_canonical[result_url] = page
            if result_url != url:
                page_by_canonical[url] = page

    return MirrorRun(pages=pages, issues=issues)


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
        fetch_url_by_canonical.setdefault(target, target_fetch_url)
        return

    nav_path = target_nav_path
    nav_parent_url: str | None = None
    if target != current_url:
        if _nav_path_points_to_current_page(target_nav_path, current_title):
            nav_parent_url = current_url
            if link_text:
                nav_path = (*target_nav_path, link_text)
        elif _nav_path_points_to_current_page(target_nav_path[:-1], current_title):
            nav_parent_url = current_url

    should_update_nav = _prefer_nav_path(nav_path, nav_path_by_canonical.get(target))
    if should_update_nav:
        nav_path_by_canonical[target] = nav_path
        if page := page_by_canonical.get(target):
            page.nav_path = nav_path

    should_update_fetch_url = should_update_nav or not extract_tocpath(fetch_url_by_canonical.get(target, ""))
    if should_update_fetch_url:
        fetch_url_by_canonical[target] = target_fetch_url
        if page := page_by_canonical.get(target):
            page.source_url = target_fetch_url

    if nav_parent_url and (target not in nav_parent_by_canonical or should_update_nav):
        nav_parent_by_canonical[target] = nav_parent_url
        if page := page_by_canonical.get(target):
            page.nav_parent_url = nav_parent_url


def _prefer_nav_path(candidate: tuple[str, ...], current: tuple[str, ...] | None) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    return len(candidate) > len(current)


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
    value = re.split(r"\s+[–-]\s+", value, maxsplit=1)[0]
    return re.sub(r"[^0-9a-zа-яё]+", "", value.lower().replace("\xa0", " "))


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
