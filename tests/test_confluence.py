from __future__ import annotations

import io
import asyncio
from pathlib import Path

import pytest

from dochive.auth import _dotenv_values, request_headers, validate_auth_config
from dochive.confluence import confluence_body_html, confluence_links_and_assets, confluence_markdown
from dochive.html_extract import inject_html_tables
from dochive.models import Asset, MirrorConfig, Page
from dochive.url_utils import canonicalize_confluence_url, url_to_markdown_relpath
from dochive.web_source import (
    NavigationEntry,
    _browser_config_kwargs,
    _canonicalize_crawl_url,
    _fetch_pages_from_navigation_index,
    _uses_madcap_structure,
)
from dochive.writer import write_mirror


def test_confluence_canonical_url_preserves_viewpage_page_id() -> None:
    first = "https://start.nau.im/pages/viewpage.action?pageId=1&src=contextnavpagetreemode"
    second = "https://start.nau.im/pages/viewpage.action?pageId=2"

    assert canonicalize_confluence_url(first) == "https://start.nau.im/pages/viewpage.action?pageId=1"
    assert canonicalize_confluence_url(second) == "https://start.nau.im/pages/viewpage.action?pageId=2"
    assert url_to_markdown_relpath(first) == Path("pages/viewpage-1.md")
    assert url_to_markdown_relpath(second) == Path("pages/viewpage-2.md")


def test_default_crawl_canonicalization_still_drops_query_and_normalizes_language_prefix() -> None:
    root = "https://example.com/ru/advices"
    target = "https://example.com/advices/work?pageId=1"

    assert _canonicalize_crawl_url(target, root) == "https://example.com/ru/advices/work"


def test_confluence_crawl_canonicalization_keeps_page_id_only_for_confluence() -> None:
    config = MirrorConfig(source="https://start.nau.im/pages/viewpage.action?pageId=1", out_dir=Path("."), source_type="confluence")

    assert _canonicalize_crawl_url(
        "https://start.nau.im/pages/viewpage.action?pageId=2&focusedCommentId=10",
        config.source,
        config,
    ) == "https://start.nau.im/pages/viewpage.action?pageId=2"


def test_confluence_source_type_does_not_use_madcap_structure() -> None:
    assert _uses_madcap_structure(MirrorConfig(source="https://example.com/docs", out_dir=Path("."))) is True
    assert _uses_madcap_structure(
        MirrorConfig(source="https://example.com/docs", out_dir=Path("."), structure_mode="links")
    ) is False
    assert _uses_madcap_structure(
        MirrorConfig(source="https://example.com/wiki", out_dir=Path("."), source_type="wikijs")
    ) is False
    assert _uses_madcap_structure(
        MirrorConfig(source="https://example.com/pages/viewpage.action?pageId=1", out_dir=Path("."), source_type="confluence")
    ) is False


def test_bearer_auth_requires_confluence_source_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCHIVE_AUTH_TOKEN", "secret-token")
    config = MirrorConfig(source="https://example.com/docs", out_dir=Path("."), auth_mode="bearer")

    with pytest.raises(RuntimeError, match="source-type confluence"):
        validate_auth_config(config)


def test_bearer_auth_requires_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCHIVE_AUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    config = MirrorConfig(
        source="https://start.nau.im/pages/viewpage.action?pageId=1",
        out_dir=Path("."),
        source_type="confluence",
        auth_mode="bearer",
    )

    with pytest.raises(RuntimeError, match="DOCHIVE_AUTH_TOKEN"):
        request_headers(config)


def test_bearer_auth_can_read_token_from_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCHIVE_AUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text('DOCHIVE_AUTH_TOKEN="dotenv-token"\n', encoding="utf-8")
    config = MirrorConfig(
        source="https://start.nau.im/pages/viewpage.action?pageId=1",
        out_dir=Path("."),
        source_type="confluence",
        auth_mode="bearer",
    )

    assert request_headers(config) == {"Authorization": "Bearer dotenv-token"}


def test_process_env_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOCHIVE_AUTH_TOKEN", "process-token")
    (tmp_path / ".env").write_text("DOCHIVE_AUTH_TOKEN=dotenv-token\n", encoding="utf-8")
    config = MirrorConfig(
        source="https://start.nau.im/pages/viewpage.action?pageId=1",
        out_dir=Path("."),
        source_type="confluence",
        auth_mode="bearer",
    )

    assert request_headers(config) == {"Authorization": "Bearer process-token"}


def test_dotenv_parser_accepts_export_and_comments(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# local secrets\nexport DOCHIVE_AUTH_TOKEN=dotenv-token # comment\n",
        encoding="utf-8",
    )

    assert _dotenv_values(tmp_path)["DOCHIVE_AUTH_TOKEN"] == "dotenv-token"


def test_confluence_bearer_auth_reaches_crawl4ai_browser_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCHIVE_AUTH_TOKEN", "secret-token")
    config = MirrorConfig(
        source="https://start.nau.im/pages/viewpage.action?pageId=1",
        out_dir=Path("."),
        source_type="confluence",
        auth_mode="bearer",
    )

    assert _browser_config_kwargs(config)["headers"] == {"Authorization": "Bearer secret-token"}


def test_confluence_asset_download_uses_auth_header_without_serializing_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCHIVE_AUTH_TOKEN", "secret-token")
    captured: dict[str, str | None] = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    def fake_urlopen(request: object, context: object = None) -> FakeResponse:
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse(b"png")

    monkeypatch.setattr("dochive.writer.urlopen", fake_urlopen)

    page_url = "https://start.nau.im/pages/viewpage.action?pageId=299440479"
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=canonicalize_confluence_url(page_url),
                title="Confluence Page",
                markdown="![Screenshot](https://start.nau.im/download/attachments/1/screen.png)\n",
                depth=0,
                assets=[Asset(source="https://start.nau.im/download/attachments/1/screen.png", kind="images")],
            )
        ],
        MirrorConfig(
            source=page_url,
            out_dir=tmp_path,
            save_asset_kinds=frozenset({"images"}),
            source_type="confluence",
            auth_mode="bearer",
        ),
    )

    assert captured["authorization"] == "Bearer secret-token"
    assert "secret-token" not in "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.yaml"))
    assert "secret-token" not in "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.md"))


class ConfluenceFakeResult:
    success = True
    status_code = 200

    def __init__(self, html: str) -> None:
        self.html = html
        self.cleaned_html = html
        self.markdown = (
            "# [Gramax — обзор](https://start.nau.im/pages/viewpage.action?pageId=299440479)\n"
            "* [View inline comments](https://start.nau.im/pages/viewpage.action?pageId=299440479)\n"
            "* [Export to Word](https://start.nau.im/exportword?pageId=299440479)\n"
            "| Page Title | Space | Updated |\n"
            "| --- | --- | --- |\n"
            "| Gramax | 02 | Today |\n"
        )
        self.metadata = {"title": "Gramax — обзор - Центральная база NAUMEN", "description": ""}
        self.links = {
            "internal": [
                {"href": "https://start.nau.im/exportword?pageId=299440479", "text": "Export to Word"},
                {"href": "https://gram.ax/resources/docs", "text": "Документация"},
            ],
            "external": [],
        }
        self.media = {"images": [{"src": "https://start.nau.im/s/en_GB/slack.png", "alt": "Slack Notification"}]}


class ConfluenceFakeCrawler:
    def __init__(self, html: str) -> None:
        self.html = html

    async def arun(self, *, url: str, config: object) -> ConfluenceFakeResult:
        return ConfluenceFakeResult(self.html)


def test_confluence_mirror_uses_body_only_and_markdown_tables() -> None:
    page_url = "https://start.nau.im/pages/viewpage.action?pageId=299440479"
    html = _confluence_fixture_html()
    config = MirrorConfig(source=page_url, out_dir=Path("."), source_type="confluence")

    pages, issues = asyncio.run(
        _fetch_pages_from_navigation_index(
            ConfluenceFakeCrawler(html),
            object(),
            config,
            {
                canonicalize_confluence_url(page_url): NavigationEntry(
                    canonical_url=canonicalize_confluence_url(page_url),
                    fetch_url=page_url,
                    depth=0,
                    order=1,
                )
            },
            root_url=canonicalize_confluence_url(page_url),
            allowed_prefixes=("https://start.nau.im/pages/viewpage.action?pageId=299440479",),
        )
    )

    assert issues == []
    markdown = pages[0].markdown
    assert "View inline comments" not in markdown
    assert "Export to Word" not in markdown
    assert "Page Title" not in markdown
    assert "Created by" not in markdown
    assert "| Компонент | Описание |" in markdown
    assert "| **Редактор (WASM)** | Полностью локально работает в браузере с Git |" in markdown
    assert "| Режим | Где работает | Хранение данных |" in markdown
    assert "| **Browser** | Браузер | OPFS (Origin Private File System) |" in markdown
    assert "https://gram.ax/resources/docs" in pages[0].links_external
    assert all("exportword" not in link for link in pages[0].links_external)
    assert pages[0].assets == []


def test_confluence_body_extraction_prefers_wiki_content_inside_main_content() -> None:
    body = confluence_body_html(_confluence_fixture_html())

    assert "Компоненты" in body
    assert "Page Title" not in body
    assert "Created by" not in body


def test_confluence_simple_tables_render_as_markdown() -> None:
    markdown = confluence_markdown(confluence_body_html(_confluence_fixture_html()), "https://start.nau.im/pages/viewpage.action?pageId=1")

    assert "| Компонент | Описание |" in markdown
    assert "<table" not in markdown


def test_confluence_body_links_preserve_viewpage_page_id() -> None:
    links, _media = confluence_links_and_assets(
        '<div class="wiki-content"><a href="/pages/viewpage.action?pageId=42&src=context">Child</a></div>',
        "https://start.nau.im/pages/viewpage.action?pageId=1",
    )

    assert links["internal"] == [{"href": "https://start.nau.im/pages/viewpage.action?pageId=42", "text": "Child"}]


def test_generic_table_injection_still_uses_html_tables() -> None:
    markdown = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    html = "<table><tbody><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></tbody></table>"

    result = inject_html_tables(markdown, html, "https://example.com/docs")

    assert '{% table header="row" %}' in result
    assert "{% /table %}" in result
    assert "| A | B |" not in result


def _confluence_fixture_html() -> str:
    return """\
<html>
<body>
<nav>
  <a href="https://start.nau.im/pages/viewpage.action?pageId=299440479">View inline comments</a>
  <a href="https://start.nau.im/exportword?pageId=299440479">Export to Word</a>
  <img src="https://start.nau.im/s/en_GB/slack.png" alt="Slack Notification">
</nav>
<table><tr><th>Page Title</th><th>Space</th><th>Updated</th></tr><tr><td>Gramax</td><td>02</td><td>Today</td></tr></table>
<main id="main-content">
  <h1>Gramax — обзор</h1>
  <div class="page-metadata">Created by Алексей Ефимов, last modified today</div>
  <div class="wiki-content">
    <p>Gramax — бесплатная платформа для технической документации с интеграцией Git.</p>
    <blockquote>ℹ️ <strong>Официальная документация</strong> Документация: <a href="https://gram.ax/resources/docs">https://gram.ax/resources/docs</a></blockquote>
    <h2>Компоненты</h2>
    <table class="confluenceTable">
      <tbody>
        <tr><th class="confluenceTh">Компонент</th><th class="confluenceTh">Описание</th></tr>
        <tr><td class="confluenceTd"><strong>Редактор (WASM)</strong></td><td class="confluenceTd">Полностью локально работает в браузере с Git</td></tr>
        <tr><td class="confluenceTd"><strong>Портал (Docportal)</strong></td><td class="confluenceTd">Клонирует репозитории и отображает документацию</td></tr>
        <tr><td class="confluenceTd"><strong>git-proxy</strong></td><td class="confluenceTd">Прокси-сервер для доступа к Git репозиториям — WASM не имеет прямого доступа из-за CORS и origin политики</td></tr>
        <tr><td class="confluenceTd"><strong>GES</strong></td><td class="confluenceTd">Gramax Enterprise Server — внешний сервис для корпоративного использования</td></tr>
      </tbody>
    </table>
    <h2>Режимы работы</h2>
    <table class="confluenceTable">
      <tbody>
        <tr><th>Режим</th><th>Где работает</th><th>Хранение данных</th></tr>
        <tr><td><strong>Tauri (Desktop)</strong></td><td>Локально</td><td>Локальная файловая система</td></tr>
        <tr><td><strong>Browser</strong></td><td>Браузер</td><td>OPFS (Origin Private File System)</td></tr>
      </tbody>
    </table>
  </div>
</main>
</body>
</html>
"""
