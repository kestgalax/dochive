from pathlib import Path

from dochive.local_source import crawl_local_html
from dochive.models import MirrorConfig


def test_max_depth_one_crawls_start_and_direct_children_only(tmp_path: Path) -> None:
    _write_page(tmp_path / "index.html", "Index", ["child-a.html", "child-b.html"])
    _write_page(tmp_path / "child-a.html", "Child A", ["grandchild.html"])
    _write_page(tmp_path / "child-b.html", "Child B", [])
    _write_page(tmp_path / "grandchild.html", "Grandchild", [])

    run = crawl_local_html(MirrorConfig(source=str(tmp_path), out_dir=tmp_path / "out", max_depth=1))

    assert [Path(page.source_path).name for page in run.pages if page.source_path] == [
        "index.html",
        "child-a.html",
        "child-b.html",
    ]
    assert all(page.depth <= 1 for page in run.pages)


def test_max_pages_limits_successfully_crawled_pages(tmp_path: Path) -> None:
    _write_page(tmp_path / "index.html", "Index", ["child-a.html", "child-b.html", "child-c.html"])
    _write_page(tmp_path / "child-a.html", "Child A", [])
    _write_page(tmp_path / "child-b.html", "Child B", [])
    _write_page(tmp_path / "child-c.html", "Child C", [])

    run = crawl_local_html(MirrorConfig(source=str(tmp_path), out_dir=tmp_path / "out", max_depth=3, max_pages=2))

    assert [Path(page.source_path).name for page in run.pages if page.source_path] == [
        "index.html",
        "child-a.html",
    ]


def test_depth_three_with_twenty_page_limit(tmp_path: Path) -> None:
    _write_page(tmp_path / "index.html", "Index", ["level1-a.html", "level1-b.html"])
    _write_page(tmp_path / "level1-a.html", "Level 1 A", ["level2-a.html"])
    _write_page(tmp_path / "level1-b.html", "Level 1 B", ["level2-b.html"])
    _write_page(tmp_path / "level2-a.html", "Level 2 A", ["level3-a.html"])
    _write_page(tmp_path / "level2-b.html", "Level 2 B", ["level3-b.html"])
    _write_page(tmp_path / "level3-a.html", "Level 3 A", ["level4-a.html"])
    _write_page(tmp_path / "level3-b.html", "Level 3 B", ["level4-b.html"])
    _write_page(tmp_path / "level4-a.html", "Level 4 A", [])
    _write_page(tmp_path / "level4-b.html", "Level 4 B", [])

    run = crawl_local_html(MirrorConfig(source=str(tmp_path), out_dir=tmp_path / "out", max_depth=3, max_pages=20))

    assert [Path(page.source_path).name for page in run.pages if page.source_path] == [
        "index.html",
        "level1-a.html",
        "level1-b.html",
        "level2-a.html",
        "level2-b.html",
        "level3-a.html",
        "level3-b.html",
    ]
    assert all(page.depth <= 3 for page in run.pages)


def test_depth_three_still_stops_at_twenty_pages(tmp_path: Path) -> None:
    child_links = [f"child-{index}.html" for index in range(1, 26)]
    _write_page(tmp_path / "index.html", "Index", child_links)
    for link in child_links:
        _write_page(tmp_path / link, link, [])

    run = crawl_local_html(MirrorConfig(source=str(tmp_path), out_dir=tmp_path / "out", max_depth=3, max_pages=20))

    assert len(run.pages) == 20
    assert [Path(page.source_path).name for page in run.pages[:3] if page.source_path] == [
        "index.html",
        "child-1.html",
        "child-2.html",
    ]
    assert Path(run.pages[-1].source_path).name == "child-19.html"


def _write_page(path: Path, title: str, links: list[str]) -> None:
    anchors = "\n".join(f'<a href="{href}">{href}</a>' for href in links)
    path.write_text(
        f"""<!doctype html>
<html>
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
{anchors}
</body>
</html>
""",
        encoding="utf-8",
    )
