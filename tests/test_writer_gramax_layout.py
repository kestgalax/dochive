from pathlib import Path, PurePosixPath

from dochive.models import Asset, MirrorConfig, Page
from dochive.writer import _asset_relpath, _relative_asset_path, write_mirror


def test_writer_uses_gramax_index_for_pages_with_children(tmp_path: Path) -> None:
    parent_url = "https://example.com/docs/beta_35.htm"
    child_url = "https://example.com/docs/kakaya-to-stranica.htm"
    flat_url = "https://example.com/docs/change_list_arch.htm"
    pages = [
        Page(
            source_url=parent_url,
            canonical_url=parent_url,
            title="Parent",
            markdown=f"[Child]({child_url})\n\n[Flat]({flat_url})\n",
            depth=0,
            links_internal=[child_url, flat_url],
        ),
        Page(
            source_url=child_url,
            canonical_url=child_url,
            title="Child",
            markdown=f"[Parent]({parent_url})\n",
            depth=1,
            parent_url=parent_url,
            links_internal=[parent_url],
        ),
        Page(
            source_url=flat_url,
            canonical_url=flat_url,
            title="Flat",
            markdown="Flat page.\n",
            depth=0,
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=parent_url, out_dir=tmp_path))

    parent_path = root / "docs" / "beta_35" / "_index.md"
    child_path = root / "docs" / "beta_35" / "kakaya-to-stranica.md"
    flat_path = root / "docs" / "change_list_arch.md"

    assert parent_path.exists()
    assert child_path.exists()
    assert flat_path.exists()
    assert not (root / "docs" / "beta_35.md").exists()
    assert "[Child](kakaya-to-stranica.md)" in parent_path.read_text(encoding="utf-8")
    assert "[Flat](../change_list_arch.md)" in parent_path.read_text(encoding="utf-8")
    assert "[Parent](_index.md)" in child_path.read_text(encoding="utf-8")

    parent_text = parent_path.read_text(encoding="utf-8")
    child_text = child_path.read_text(encoding="utf-8")
    pages_catalog = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")
    links_catalog = (root / "_catalog" / "links.yaml").read_text(encoding="utf-8")

    assert 'path: "docs/beta_35/_index.md"' in parent_text
    assert 'children:\n  - "docs/beta_35/kakaya-to-stranica.md"' in parent_text
    assert 'parent: "docs/beta_35/_index.md"' in child_text
    assert 'path: "docs/beta_35/_index.md"' in pages_catalog
    assert 'path: "docs/beta_35/kakaya-to-stranica.md"' in pages_catalog
    assert 'path: "docs/change_list_arch.md"' in pages_catalog
    assert 'to: "docs/beta_35/_index.md"' in links_catalog
    assert 'to: "docs/beta_35/kakaya-to-stranica.md"' in links_catalog


def test_index_page_assets_stay_beside_index_file() -> None:
    page_relpath = PurePosixPath("docs/beta_35/_index.md")
    asset = Asset(source="https://example.com/assets/example.png", kind="images")
    local_path = _asset_relpath(asset, page_relpath).as_posix()

    assert local_path.startswith("docs/beta_35/example-")
    assert "/_index/" not in local_path
    assert (
        _relative_asset_path(Asset(asset.source, asset.kind, local_path=local_path), page_relpath)
        == f"./{PurePosixPath(local_path).name}"
    )
