from __future__ import annotations

from pathlib import Path, PurePosixPath

from dochive.models import MirrorConfig, Page
from dochive.writer import _folders_to_refresh, _path_in_roots, _read_catalog_items, write_mirror


def test_partial_run_rewrites_links_to_previously_mirrored_pages(tmp_path: Path) -> None:
    target_url = "https://example.com/docs/QuickStart/QuickStart.htm"
    source_url = "https://example.com/docs/introduction/introduction.htm"
    config = MirrorConfig(source=source_url, out_dir=tmp_path)

    write_mirror(
        [
            Page(
                source_url=target_url,
                canonical_url=target_url,
                title="Quick Start",
                markdown="# Quick Start\n",
                depth=0,
                nav_path=("Quick Start",),
            ),
        ],
        config,
    )

    write_mirror(
        [
            Page(
                source_url=source_url,
                canonical_url=source_url,
                title="Introduction",
                markdown=(
                    "# Introduction\n\n"
                    f"- [Quick Start]({target_url})\n"
                    f"- [Off site](https://other.example.com/page)\n"
                ),
                depth=0,
                nav_path=("Introduction",),
                links_external=[target_url, "https://other.example.com/page"],
            ),
        ],
        config,
    )

    intro_path = tmp_path / "example.com" / "docs" / "introduction" / "introduction.md"
    content = intro_path.read_text(encoding="utf-8")
    assert "[Quick Start](../quickstart/quickstart.md)" in content
    assert target_url not in content
    assert "https://other.example.com/page" in content
    assert "docs/quickstart/quickstart.md" in content
    assert target_url not in content.split("---\n\n", 2)[1]


def test_partial_mirror_preserves_other_section_catalog_and_disk(tmp_path: Path) -> None:
    intro_url = "https://example.com/docs/introduction/introduction.htm"
    quickstart_url = "https://example.com/docs/QuickStart/QuickStart.htm"
    intro_markdown = "# Introduction\n\nIntro body preserved.\n"
    root = tmp_path / "example.com"

    write_mirror(
        [
            Page(
                source_url=intro_url,
                canonical_url=intro_url,
                title="Introduction",
                markdown=intro_markdown,
                depth=0,
                nav_path=("Introduction",),
            ),
        ],
        MirrorConfig(source=intro_url, out_dir=tmp_path),
    )

    intro_path = tmp_path / "example.com" / "docs" / "introduction" / "introduction.md"
    assert "Intro body preserved." in intro_path.read_text(encoding="utf-8")

    write_mirror(
        [
            Page(
                source_url=quickstart_url,
                canonical_url=quickstart_url,
                title="Quick Start",
                markdown="# Quick Start\n\nQuick start body.\n",
                depth=0,
                nav_path=("Quick Start",),
            ),
        ],
        MirrorConfig(source=quickstart_url, out_dir=tmp_path),
    )

    intro_content = intro_path.read_text(encoding="utf-8")
    assert "Intro body preserved." in intro_content
    assert "ожидает отдельного зеркалирования" not in intro_content

    catalog_pages = _read_catalog_items(root / "_catalog" / "pages.yaml", "pages")
    intro_entries = [page for page in catalog_pages if page.get("canonical_url") == intro_url]
    quickstart_entries = [page for page in catalog_pages if page.get("canonical_url") == quickstart_url]
    assert len(intro_entries) == 1
    assert intro_entries[0].get("placeholder") is not True
    assert len(quickstart_entries) == 1


def test_folders_to_refresh_limits_partial_sync_scope() -> None:
    all_folders = {
        PurePosixPath("docs/content/introduction"),
        PurePosixPath("docs/content/introduction/plan"),
        PurePosixPath("docs/content/quickstart"),
        PurePosixPath("docs/content"),
        PurePosixPath("docs"),
        PurePosixPath("."),
    }
    sync_roots = (PurePosixPath("docs/content/introduction/_index.md"),)
    refresh = _folders_to_refresh(all_folders, sync_roots)
    assert refresh is not None
    assert PurePosixPath("docs/content/quickstart") not in refresh
    assert PurePosixPath("docs/content/introduction/plan") in refresh
    assert PurePosixPath("docs/content") in refresh


def test_path_in_roots_uses_folder_scope_for_page_paths() -> None:
    sync_roots = (PurePosixPath("docs/content/introduction/_index.md"),)
    assert _path_in_roots("docs/content/introduction/plan/_index.md", sync_roots)
    assert not _path_in_roots("docs/content/quickstart/_index.md", sync_roots)
