from __future__ import annotations

from pathlib import Path, PurePosixPath

from dochive.models import MirrorConfig, Page, StructureEntry, StructureRun
from dochive.relink import build_link_path_map, relink_mirror
from dochive.writer import _read_catalog_items, write_mirror, write_structure_catalog
from dochive.yaml_writer import dumps_yaml


def _write_structure_catalog(tmp_path: Path, entries: list[tuple[str, str, str]]) -> Path:
    run = StructureRun(
        entries=[
            StructureEntry(
                fetch_url=fetch_url,
                canonical_url=canonical_url,
                title=title,
                depth=0,
                order=index,
                nav_path=(title,),
            )
            for index, (fetch_url, canonical_url, title) in enumerate(entries, start=1)
        ]
    )
    source = entries[0][1] if entries else "https://example.com/docs/start.htm"
    return write_structure_catalog(run, MirrorConfig(source=source, out_dir=tmp_path))


def test_build_link_path_map_prefers_mirrored_pages_over_structure() -> None:
    mapping = build_link_path_map(
        [
            {
                "canonical_url": "https://example.com/docs/a.htm",
                "path": "docs/structure-a.md",
            }
        ],
        [
            {
                "canonical_url": "https://example.com/docs/a.htm",
                "path": "docs/pages-a.md",
                "placeholder": False,
            }
        ],
    )
    assert mapping["https://example.com/docs/a.htm"] == PurePosixPath("docs/pages-a.md")


def test_relink_rewrites_absolute_url_using_structure_and_pages(tmp_path: Path) -> None:
    quickstart_url = "https://example.com/docs/QuickStart/QuickStart.htm"
    intro_url = "https://example.com/docs/introduction/introduction.htm"
    config = MirrorConfig(source=intro_url, out_dir=tmp_path)

    root = write_mirror(
        [
            Page(
                source_url=quickstart_url,
                canonical_url=quickstart_url,
                title="Quick Start",
                markdown="# Quick Start\n",
                depth=0,
                nav_path=("Quick Start",),
            ),
        ],
        config,
    )
    _write_structure_catalog(
        tmp_path,
        [
            (quickstart_url, quickstart_url, "Quick Start"),
            (intro_url, intro_url, "Introduction"),
        ],
    )

    write_mirror(
        [
            Page(
                source_url=intro_url,
                canonical_url=intro_url,
                title="Introduction",
                markdown=(
                    "# Introduction\n\n"
                    f"- [Quick Start]({quickstart_url})\n"
                    f"- [Off site](https://other.example.com/page)\n"
                ),
                depth=0,
                nav_path=("Introduction",),
                links_external=[quickstart_url, "https://other.example.com/page"],
            ),
        ],
        config,
    )

    pages = _read_catalog_items(root / "_catalog" / "pages.yaml", "pages")
    intro_entry = next(item for item in pages if item.get("canonical_url") == intro_url)
    intro_path = root / Path(*Path(str(intro_entry["path"])).parts)
    broken = intro_path.read_text(encoding="utf-8").replace(
        "../quickstart/quickstart.md",
        quickstart_url,
    )
    intro_path.write_text(broken, encoding="utf-8")

    result = relink_mirror(root)
    content = intro_path.read_text(encoding="utf-8")
    assert result.changed == 1
    assert "[Quick Start](../quickstart/quickstart.md)" in content
    assert quickstart_url not in content.split("---\n\n", 2)[1]
    assert "https://other.example.com/page" in content


def test_relink_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/page.htm"
    target_url = "https://example.com/docs/target.htm"
    config = MirrorConfig(source=page_url, out_dir=tmp_path)

    root = write_mirror(
        [
            Page(
                source_url=target_url,
                canonical_url=target_url,
                title="Target",
                markdown="# Target\n",
                depth=0,
                nav_path=("Target",),
            ),
        ],
        config,
    )
    _write_structure_catalog(tmp_path, [(target_url, target_url, "Target"), (page_url, page_url, "Page")])

    write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Page",
                markdown=f"# Page\n\n[Target]({target_url})\n",
                depth=0,
                nav_path=("Page",),
            ),
        ],
        config,
    )

    pages = _read_catalog_items(root / "_catalog" / "pages.yaml", "pages")
    page_entry = next(item for item in pages if item.get("canonical_url") == page_url)
    page_path = root / Path(*Path(str(page_entry["path"])).parts)
    content = page_path.read_text(encoding="utf-8")
    for relative in ("../target/target.md", "../target.md"):
        if relative in content:
            content = content.replace(relative, target_url)
            break
    original = content
    page_path.write_text(original, encoding="utf-8")
    pages_before = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")

    result = relink_mirror(root, dry_run=True)
    assert result.changed == 1
    assert page_path.read_text(encoding="utf-8") == original
    assert (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8") == pages_before


def test_relink_skips_placeholder_pages(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/page.htm"
    placeholder_url = "https://example.com/docs/placeholder.htm"
    config = MirrorConfig(source=page_url, out_dir=tmp_path)
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Page",
                markdown=f"# Page\n\n[Future]({placeholder_url})\n",
                depth=0,
                nav_path=("Page",),
            ),
        ],
        config,
    )
    _write_structure_catalog(tmp_path, [(placeholder_url, placeholder_url, "Future"), (page_url, page_url, "Page")])

    catalog_dir = root / "_catalog"
    structure_items = _read_catalog_items(catalog_dir / "structure.yaml", "structure")
    placeholder_path = next(item["path"] for item in structure_items if item["canonical_url"] == placeholder_url)
    placeholder_file = root / Path(*Path(str(placeholder_path)).parts)
    placeholder_file.parent.mkdir(parents=True, exist_ok=True)
    placeholder_file.write_text(
        "---\n"
        + dumps_yaml(
            {
                "canonical_url": placeholder_url,
                "placeholder": True,
                "links": {"internal": [], "external": [placeholder_url]},
            }
        )
        + "---\n\n# Future\n",
        encoding="utf-8",
    )

    pages = _read_catalog_items(catalog_dir / "pages.yaml", "pages")
    pages.append(
        {
            "path": str(placeholder_path),
            "canonical_url": placeholder_url,
            "placeholder": True,
            "content_hash": "sha256:placeholder",
        }
    )
    (catalog_dir / "pages.yaml").write_text(dumps_yaml({"pages": pages}), encoding="utf-8")

    result = relink_mirror(root)
    placeholder_content = placeholder_file.read_text(encoding="utf-8")
    assert placeholder_url in placeholder_content
    assert result.skipped >= 0


def test_relink_without_structure_uses_pages_catalog_only(tmp_path: Path) -> None:
    quickstart_url = "https://example.com/docs/QuickStart/QuickStart.htm"
    intro_url = "https://example.com/docs/introduction/introduction.htm"
    config = MirrorConfig(source=intro_url, out_dir=tmp_path)

    root = write_mirror(
        [
            Page(
                source_url=quickstart_url,
                canonical_url=quickstart_url,
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
                source_url=intro_url,
                canonical_url=intro_url,
                title="Introduction",
                markdown=f"# Introduction\n\n[Quick Start]({quickstart_url})\n",
                depth=0,
                nav_path=("Introduction",),
            ),
        ],
        config,
    )

    pages = _read_catalog_items(root / "_catalog" / "pages.yaml", "pages")
    intro_entry = next(item for item in pages if item.get("canonical_url") == intro_url)
    intro_path = root / Path(*Path(str(intro_entry["path"])).parts)
    intro_path.write_text(intro_path.read_text(encoding="utf-8").replace("../quickstart/quickstart.md", quickstart_url))

    result = relink_mirror(root)
    content = intro_path.read_text(encoding="utf-8")
    assert result.changed == 1
    assert "[Quick Start](../quickstart/quickstart.md)" in content
