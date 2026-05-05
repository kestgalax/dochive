from pathlib import Path, PurePosixPath

from dochive.models import Asset, MirrorConfig, Page
from dochive.writer import _asset_relpath, _normalize_media_spacing, _relative_asset_path, write_mirror


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
            nav_parent_url=parent_url,
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
    assert "order: 1" in parent_text
    assert 'children:\n  - "docs/beta_35/kakaya-to-stranica.md"' in parent_text
    assert 'parent: "docs/beta_35/_index.md"' in child_text
    assert "order: 1" in child_text
    assert 'path: "docs/beta_35/_index.md"' in pages_catalog
    assert 'path: "docs/beta_35/kakaya-to-stranica.md"' in pages_catalog
    assert 'path: "docs/change_list_arch.md"' in pages_catalog
    assert "order: 2" in pages_catalog
    assert 'to: "docs/beta_35/_index.md"' in links_catalog
    assert 'to: "docs/beta_35/kakaya-to-stranica.md"' in links_catalog


def test_writer_collapses_duplicate_section_filename_for_index_page(tmp_path: Path) -> None:
    parent_url = "https://example.com/docs/QuickStartSDPro/QuickStartSDPro.htm"
    child_url = "https://example.com/docs/QuickStartSDPro/1.htm"
    root = write_mirror(
        [
            Page(
                source_url=parent_url,
                canonical_url=parent_url,
                title="Quick Start",
                markdown=f"[Step 1]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Step 1",
                markdown="Step.\n",
                depth=1,
                nav_parent_url=parent_url,
            ),
        ],
        MirrorConfig(source=parent_url, out_dir=tmp_path),
    )

    parent_path = root / "docs" / "quickstartsdpro" / "_index.md"
    child_path = root / "docs" / "quickstartsdpro" / "1.md"

    assert parent_path.exists()
    assert child_path.exists()
    assert not (root / "docs" / "quickstartsdpro" / "quickstartsdpro" / "_index.md").exists()
    assert "[Step 1](1.md)" in parent_path.read_text(encoding="utf-8")
    assert 'parent: "docs/quickstartsdpro/_index.md"' in child_path.read_text(encoding="utf-8")


def test_writer_does_not_nest_context_links_without_nav_parent(tmp_path: Path) -> None:
    source_url = "https://example.com/docs/current.htm"
    target_url = "https://example.com/docs/other-section/target.htm"
    pages = [
        Page(
            source_url=source_url,
            canonical_url=source_url,
            title="Current",
            markdown=f"[Context]({target_url})\n",
            depth=0,
            links_internal=[target_url],
        ),
        Page(
            source_url=target_url,
            canonical_url=target_url,
            title="Target",
            markdown="Target page.\n",
            depth=1,
            parent_url=source_url,
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=source_url, out_dir=tmp_path))

    source_path = root / "docs" / "current.md"
    target_path = root / "docs" / "other-section" / "target.md"

    assert source_path.exists()
    assert target_path.exists()
    assert not (root / "docs" / "current" / "_index.md").exists()
    assert "[Context](other-section/target.md)" in source_path.read_text(encoding="utf-8")
    assert 'parent: null' in target_path.read_text(encoding="utf-8")


def test_writer_uses_nav_path_instead_of_discovery_parent(tmp_path: Path) -> None:
    root_url = "https://example.com/docs/root.htm"
    wrong_discovery_url = "https://example.com/docs/context.htm"
    parent_url = "https://example.com/docs/parent.htm"
    child_url = "https://example.com/docs/child.htm"
    pages = [
        Page(
            source_url=wrong_discovery_url,
            canonical_url=wrong_discovery_url,
            title="Context",
            markdown=f"[Child]({child_url})\n",
            depth=0,
            links_internal=[child_url],
        ),
        Page(
            source_url=parent_url,
            canonical_url=parent_url,
            title="Parent",
            markdown="Parent.\n",
            depth=1,
            nav_path=("Root", "Parent"),
        ),
        Page(
            source_url=child_url,
            canonical_url=child_url,
            title="Child",
            markdown="Child.\n",
            depth=1,
            parent_url=wrong_discovery_url,
            nav_path=("Root", "Parent", "Child"),
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=root_url, out_dir=tmp_path))

    parent_path = root / "docs" / "parent" / "_index.md"
    child_path = root / "docs" / "parent" / "child.md"
    context_path = root / "docs" / "context.md"

    assert parent_path.exists()
    assert child_path.exists()
    assert context_path.exists()
    assert 'parent: "docs/parent/_index.md"' in child_path.read_text(encoding="utf-8")
    assert 'children:\n  - "docs/parent/child.md"' in parent_path.read_text(encoding="utf-8")


def test_writer_ignores_self_nav_parent(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/current.htm"
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Current",
                markdown="Current.\n",
                depth=0,
                nav_parent_url=page_url,
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )

    text = (root / "docs" / "current.md").read_text(encoding="utf-8")

    assert "parent: null" in text
    assert "children:\n  []" in text


def test_writer_removes_stale_flat_page_when_it_becomes_index(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/quickstart/6.htm"
    child_url = "https://example.com/docs/quickstart/work_portal.htm"

    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Step 6",
                markdown="Step.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )
    flat_path = root / "docs" / "quickstart" / "6.md"

    assert flat_path.exists()

    write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Step 6",
                markdown=f"[Portal]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Portal",
                markdown="Portal.\n",
                depth=1,
                nav_parent_url=page_url,
            ),
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )

    assert not flat_path.exists()
    assert (root / "docs" / "quickstart" / "6" / "_index.md").exists()
    assert (root / "docs" / "quickstart" / "6" / "work_portal.md").exists()


def test_writer_removes_stale_catalog_page_when_nav_parent_changes(tmp_path: Path) -> None:
    source_url = "https://example.com/docs/root.htm"
    old_parent_url = "https://example.com/docs/old.htm"
    new_parent_url = "https://example.com/docs/new.htm"
    child_url = "https://example.com/docs/child.htm"

    root = write_mirror(
        [
            Page(
                source_url=old_parent_url,
                canonical_url=old_parent_url,
                title="Old",
                markdown=f"[Child]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Child",
                markdown="Child.\n",
                depth=1,
                nav_parent_url=old_parent_url,
            ),
        ],
        MirrorConfig(source=source_url, out_dir=tmp_path),
    )
    old_child_path = root / "docs" / "old" / "child.md"

    assert old_child_path.exists()

    write_mirror(
        [
            Page(
                source_url=new_parent_url,
                canonical_url=new_parent_url,
                title="New",
                markdown=f"[Child]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Child",
                markdown="Child.\n",
                depth=1,
                nav_parent_url=new_parent_url,
            ),
        ],
        MirrorConfig(source=source_url, out_dir=tmp_path),
    )

    assert not old_child_path.exists()
    assert (root / "docs" / "new" / "child.md").exists()


def test_writer_preserves_other_mirrored_sections_between_runs(tmp_path: Path) -> None:
    intro_url = "https://example.com/docs/sd/nsdpro/Content/introduction/introduction.htm"
    change_url = "https://example.com/docs/sd/nsdpro/Content/Change_List/Change_List.htm"

    root = write_mirror(
        [
            Page(
                source_url=intro_url,
                canonical_url=intro_url,
                title="Introduction",
                markdown="Intro.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=intro_url, out_dir=tmp_path),
    )
    intro_path = root / "docs" / "sd" / "nsdpro" / "content" / "introduction" / "introduction.md"

    assert intro_path.exists()

    write_mirror(
        [
            Page(
                source_url=change_url,
                canonical_url=change_url,
                title="Change List",
                markdown="Changes.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=change_url, out_dir=tmp_path),
    )

    pages_catalog = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")
    content_index = (root / "docs" / "sd" / "nsdpro" / "content" / "_index.yaml").read_text(encoding="utf-8")

    assert intro_path.exists()
    assert 'path: "docs/sd/nsdpro/content/introduction/introduction.md"' in pages_catalog
    assert 'path: "docs/sd/nsdpro/content/change_list/change_list.md"' in pages_catalog
    assert 'path: "introduction"' in content_index
    assert 'path: "change_list"' in content_index
    assert 'deleted:\n  []' in (root / "_catalog" / "sync.yaml").read_text(encoding="utf-8")


def test_writer_uses_placeholder_path_for_followup_run(tmp_path: Path) -> None:
    intro_url = "https://example.com/docs/sd/nsdpro/Content/introduction/introduction.htm"
    change_url = "https://example.com/docs/sd/nsdpro/Content/Change_List/Change_List.htm"
    stable_url = "https://example.com/docs/sd/nsdpro/Content/Change_List/stable-26.htm"

    root = write_mirror(
        [
            Page(
                source_url=intro_url,
                canonical_url=intro_url,
                title="Introduction",
                markdown=f"[Change List]({change_url})\n",
                depth=0,
                nav_path=("Introduction",),
                links_external=[change_url],
            ),
            Page(
                source_url=change_url,
                canonical_url=change_url,
                title="Change List",
                markdown="# Change List\n\nРаздел ожидает отдельного зеркалирования.\n",
                depth=1,
                nav_parent_url=intro_url,
                nav_path=("Introduction", "Change List"),
                placeholder=True,
            ),
        ],
        MirrorConfig(source=intro_url, out_dir=tmp_path),
    )

    placeholder_path = root / "docs" / "sd" / "nsdpro" / "content" / "introduction" / "change_list" / "_index.md"
    intro_path = root / "docs" / "sd" / "nsdpro" / "content" / "introduction" / "_index.md"

    assert placeholder_path.exists()
    assert 'page_type: "placeholder"' in placeholder_path.read_text(encoding="utf-8")
    assert "[Change List](change_list/_index.md)" in intro_path.read_text(encoding="utf-8")
    assert 'canonical_url: "https://example.com/docs/sd/nsdpro/Content/Change_List/Change_List.htm"' in (
        root / "_catalog" / "pages.yaml"
    ).read_text(encoding="utf-8")
    assert 'placeholder: true' in (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")

    write_mirror(
        [
            Page(
                source_url=change_url,
                canonical_url=change_url,
                title="Change List",
                markdown=f"[Stable]({stable_url})\n",
                depth=0,
                nav_path=("Introduction", "Change List"),
                links_internal=[stable_url],
            ),
            Page(
                source_url=stable_url,
                canonical_url=stable_url,
                title="Stable",
                markdown="Stable content.\n",
                depth=1,
                nav_parent_url=change_url,
            ),
        ],
        MirrorConfig(source=change_url, out_dir=tmp_path),
    )

    updated_text = placeholder_path.read_text(encoding="utf-8")
    stable_path = root / "docs" / "sd" / "nsdpro" / "content" / "introduction" / "change_list" / "stable-26.md"

    assert stable_path.exists()
    assert 'page_type: "doc"' in updated_text
    assert "Раздел ожидает отдельного зеркалирования" not in updated_text
    assert not (root / "docs" / "sd" / "nsdpro" / "content" / "change_list" / "change_list.md").exists()
    assert 'parent: "docs/sd/nsdpro/content/introduction/change_list/_index.md"' in stable_path.read_text(
        encoding="utf-8"
    )


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


def test_writer_separates_media_tags_with_blank_lines() -> None:
    markdown = "Before.\n<video path=\"./demo.mp4\"/>\nAfter.\n<image src=\"./demo.png\"/>\nDone."

    assert _normalize_media_spacing(markdown) == (
        "Before.\n\n"
        "<video path=\"./demo.mp4\"/>\n\n"
        "After.\n\n"
        "<image src=\"./demo.png\"/>\n\n"
        "Done."
    )


def test_writer_rewrites_original_anchor_to_gramax_heading(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/beta_35.htm"
    page = Page(
        source_url=page_url,
        canonical_url=page_url,
        title="Release Notes",
        markdown="[3.5.6](#356)\n\n[Absolute](https://example.com/docs/beta_35.htm#356)\n",
        depth=0,
        anchor_headings={"356": "Release 3.5.6"},
    )

    root = write_mirror([page], MirrorConfig(source=page_url, out_dir=tmp_path))
    text = (root / "docs" / "beta_35.md").read_text(encoding="utf-8")

    assert "[3.5.6](#Release 3.5.6)" in text
    assert "[Absolute](#Release 3.5.6)" in text
    assert "beta_35.md#356" not in text


def test_writer_creates_gramax_doc_root_next_to_content_folder(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/sd/nsdpro/Content/page.htm"
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Page",
                markdown="Content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )

    doc_root = root / "docs" / "sd" / "nsdpro" / ".doc-root.yaml"

    assert doc_root.read_text(encoding="utf-8") == (
        "title: nsdpro\n"
        "syntax: XML\n"
        "supportedLanguages: []\n"
        "properties: []\n"
    )


def test_writer_does_not_overwrite_existing_doc_root(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/sd/nsdpro/Content/page.htm"
    doc_root = tmp_path / "example.com" / "docs" / "sd" / "nsdpro" / ".doc-root.yaml"
    doc_root.parent.mkdir(parents=True)
    doc_root.write_text("title: Existing\nsyntax: XML\n", encoding="utf-8")

    write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Page",
                markdown="Content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )

    assert doc_root.read_text(encoding="utf-8") == "title: Existing\nsyntax: XML\n"
