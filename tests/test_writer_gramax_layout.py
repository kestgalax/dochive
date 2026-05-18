from pathlib import Path, PurePosixPath

from dochive.models import Asset, MirrorConfig, Page, StructureEntry, StructureRun
from dochive.writer import (
    _asset_relpath,
    _normalize_media_spacing,
    _relative_asset_path,
    write_mirror,
    write_structure_catalog,
)


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


def test_writer_keeps_url_root_at_doc_root(tmp_path: Path) -> None:
    root_url = "https://example.com/"
    child_url = "https://example.com/ru/advices"

    root = write_structure_catalog(
        StructureRun(
            entries=[
                StructureEntry(
                    canonical_url=root_url,
                    fetch_url=root_url,
                    title="Home",
                    depth=0,
                    order=1,
                ),
                StructureEntry(
                    canonical_url=child_url,
                    fetch_url=child_url,
                    title="Advices",
                    depth=1,
                    order=2,
                    nav_parent_url=root_url,
                ),
            ]
        ),
        MirrorConfig(source=root_url, out_dir=tmp_path),
    )

    structure_text = (root / "_catalog" / "structure.yaml").read_text(encoding="utf-8")

    assert 'path: "_index.md"' in structure_text
    assert 'path: "ru/advices/_index.md"' in structure_text
    assert 'path: "index/ru/advices/_index.md"' not in structure_text


def test_writer_collapses_duplicate_section_filename_for_index_page(tmp_path: Path) -> None:
    parent_url = "https://example.com/docs/QuickStart/QuickStart.htm"
    child_url = "https://example.com/docs/QuickStart/1.htm"
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

    parent_path = root / "docs" / "quickstart" / "_index.md"
    child_path = root / "docs" / "quickstart" / "1.md"

    assert parent_path.exists()
    assert child_path.exists()
    assert not (root / "docs" / "quickstart" / "quickstart" / "_index.md").exists()
    assert "[Step 1](1.md)" in parent_path.read_text(encoding="utf-8")
    assert 'parent: "docs/quickstart/_index.md"' in child_path.read_text(encoding="utf-8")


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


def test_writer_resolves_duplicate_paths_with_source_section(tmp_path: Path) -> None:
    root_url = "https://example.com/docs/root.htm"
    parent_url = "https://example.com/docs/all_requests.htm"
    im_url = "https://example.com/docs/im/functionality.htm"
    req_url = "https://example.com/docs/req/functionality.htm"
    pages = [
        Page(
            source_url=parent_url,
            canonical_url=parent_url,
            title="All Requests",
            markdown=f"[IM]({im_url})\n\n[REQ]({req_url})\n",
            depth=0,
            links_internal=[im_url, req_url],
        ),
        Page(
            source_url=im_url,
            canonical_url=im_url,
            title="Functionality",
            markdown="IM.\n",
            depth=1,
            nav_parent_url=parent_url,
        ),
        Page(
            source_url=req_url,
            canonical_url=req_url,
            title="Functionality",
            markdown="REQ.\n",
            depth=1,
            nav_parent_url=parent_url,
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=root_url, out_dir=tmp_path))

    assert (root / "docs" / "all_requests" / "functionality.md").exists()
    assert (root / "docs" / "all_requests" / "req-functionality.md").exists()
    assert "[REQ](req-functionality.md)" in (root / "docs" / "all_requests" / "_index.md").read_text(
        encoding="utf-8"
    )


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


def test_writer_prefers_nav_path_parent_over_conflicting_nav_parent_url(tmp_path: Path) -> None:
    root_url = "https://example.com/docs/root.htm"
    wrong_parent_url = "https://example.com/docs/main_page.htm"
    parent_url = "https://example.com/docs/intro.htm"
    child_url = "https://example.com/docs/change_list.htm"
    pages = [
        Page(
            source_url=wrong_parent_url,
            canonical_url=wrong_parent_url,
            title="Main",
            markdown=f"[Child]({child_url})\n",
            depth=0,
            links_internal=[child_url],
        ),
        Page(
            source_url=parent_url,
            canonical_url=parent_url,
            title="Intro",
            markdown="Intro.\n",
            depth=1,
            nav_path=("Intro",),
        ),
        Page(
            source_url=child_url,
            canonical_url=child_url,
            title="Changes",
            markdown="Changes.\n",
            depth=1,
            nav_parent_url=wrong_parent_url,
            nav_path=("Intro", "Changes"),
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=root_url, out_dir=tmp_path))

    assert (root / "docs" / "intro" / "_index.md").exists()
    assert (root / "docs" / "intro" / "change_list.md").exists()
    assert not (root / "docs" / "main_page" / "change_list.md").exists()
    assert 'parent: "docs/intro/_index.md"' in (root / "docs" / "intro" / "change_list.md").read_text(
        encoding="utf-8"
    )


def test_writer_keeps_single_segment_nav_path_at_top_level(tmp_path: Path) -> None:
    source_url = "https://example.com/docs/root.htm"
    intro_url = "https://example.com/docs/introduction/introduction.htm"
    admin_url = "https://example.com/docs/admin_applied/admin_applied.htm"
    pages = [
        Page(
            source_url=intro_url,
            canonical_url=intro_url,
            title="Intro",
            markdown="Intro.\n",
            depth=1,
            nav_path=("Intro",),
            placeholder=True,
        ),
        Page(
            source_url=admin_url,
            canonical_url=admin_url,
            title="Admin",
            markdown="Admin.\n",
            depth=1,
            nav_parent_url=intro_url,
            nav_path=("Admin",),
            placeholder=True,
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=source_url, out_dir=tmp_path))

    assert (root / "docs" / "introduction" / "_index.md").exists()
    assert (root / "docs" / "admin_applied" / "_index.md").exists()
    assert not (root / "docs" / "introduction" / "admin_applied" / "_index.md").exists()
    assert 'parent: null' in (root / "docs" / "admin_applied" / "_index.md").read_text(encoding="utf-8")


def test_writer_lays_out_parent_before_earlier_discovered_child(tmp_path: Path) -> None:
    root_url = "https://example.com/docs/root.htm"
    archive_url = "https://example.com/docs/change_list/archive.htm"
    release_url = "https://example.com/docs/change_list/release_281.htm"
    child_url = "https://example.com/docs/portal/zam.htm"
    pages = [
        Page(
            source_url=child_url,
            canonical_url=child_url,
            title="Zam",
            markdown="Zam.\n",
            depth=1,
            nav_parent_url="https://example.com/docs/work_portal.htm",
            nav_path=("Intro", "Archive", "Release 2.8.1", "Zam"),
        ),
        Page(
            source_url=archive_url,
            canonical_url=archive_url,
            title="Archive",
            markdown="Archive.\n",
            depth=1,
            nav_path=("Intro", "Archive"),
        ),
        Page(
            source_url=release_url,
            canonical_url=release_url,
            title="Release 2.8.1",
            markdown="Release.\n",
            depth=2,
            nav_path=("Intro", "Archive", "Release 2.8.1"),
        ),
    ]

    root = write_mirror(pages, MirrorConfig(source=root_url, out_dir=tmp_path))

    assert (root / "docs" / "change_list" / "archive" / "release_281" / "_index.md").exists()
    assert (root / "docs" / "change_list" / "archive" / "release_281" / "zam.md").exists()
    assert not (root / "docs" / "change_list" / "release_281" / "zam.md").exists()


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
    intro_url = "https://example.com/docs/product_docs/Content/introduction/introduction.htm"
    change_url = "https://example.com/docs/product_docs/Content/Change_List/Change_List.htm"

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
    intro_path = root / "docs" / "product_docs" / "content" / "introduction" / "introduction.md"

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
    content_index = (root / "docs" / "product_docs" / "content" / "_index.yaml").read_text(encoding="utf-8")

    assert intro_path.exists()
    assert 'path: "docs/product_docs/content/introduction/introduction.md"' in pages_catalog
    assert 'path: "docs/product_docs/content/change_list/change_list.md"' in pages_catalog
    assert 'path: "introduction"' in content_index
    assert 'path: "change_list"' in content_index
    assert 'deleted:\n  []' in (root / "_catalog" / "sync.yaml").read_text(encoding="utf-8")


def test_writer_preserves_same_folder_pages_between_single_page_runs(tmp_path: Path) -> None:
    first_url = "https://example.com/docs/section/first.htm"
    second_url = "https://example.com/docs/section/second.htm"

    root = write_mirror(
        [
            Page(
                source_url=first_url,
                canonical_url=first_url,
                title="First",
                markdown="First content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=first_url, out_dir=tmp_path),
    )
    first_path = root / "docs" / "section" / "first.md"

    assert first_path.exists()

    write_mirror(
        [
            Page(
                source_url=second_url,
                canonical_url=second_url,
                title="Second",
                markdown="Second content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=second_url, out_dir=tmp_path),
    )

    pages_catalog = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")
    section_index = (root / "docs" / "section" / "_index.yaml").read_text(encoding="utf-8")

    assert first_path.exists()
    assert (root / "docs" / "section" / "second.md").exists()
    assert 'path: "docs/section/first.md"' in pages_catalog
    assert 'path: "docs/section/second.md"' in pages_catalog
    assert 'path: "docs/section/first.md"' in section_index
    assert 'path: "docs/section/second.md"' in section_index
    assert 'deleted:\n  []' in (root / "_catalog" / "sync.yaml").read_text(encoding="utf-8")


def test_writer_uses_placeholder_path_for_followup_run(tmp_path: Path) -> None:
    intro_url = "https://example.com/docs/product_docs/Content/introduction/introduction.htm"
    change_url = "https://example.com/docs/product_docs/Content/Change_List/Change_List.htm"
    stable_url = "https://example.com/docs/product_docs/Content/Change_List/stable-26.htm"

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

    placeholder_path = root / "docs" / "product_docs" / "content" / "introduction" / "change_list" / "_index.md"
    intro_path = root / "docs" / "product_docs" / "content" / "introduction" / "_index.md"

    assert placeholder_path.exists()
    assert 'page_type: "placeholder"' in placeholder_path.read_text(encoding="utf-8")
    assert "[Change List](change_list/_index.md)" in intro_path.read_text(encoding="utf-8")
    assert 'canonical_url: "https://example.com/docs/product_docs/Content/Change_List/Change_List.htm"' in (
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
    stable_path = root / "docs" / "product_docs" / "content" / "introduction" / "change_list" / "stable-26.md"

    assert stable_path.exists()
    assert 'page_type: "doc"' in updated_text
    assert "Раздел ожидает отдельного зеркалирования" not in updated_text
    assert not (root / "docs" / "product_docs" / "content" / "change_list" / "change_list.md").exists()
    assert 'parent: "docs/product_docs/content/introduction/change_list/_index.md"' in stable_path.read_text(
        encoding="utf-8"
    )


def test_writer_uses_saved_structure_for_followup_run(tmp_path: Path) -> None:
    intro_url = "https://example.com/docs/product_docs/Content/introduction/introduction.htm"
    change_url = "https://example.com/docs/product_docs/Content/Change_List/Change_List.htm"
    stable_url = "https://example.com/docs/product_docs/Content/Change_List/stable-26.htm"
    config = MirrorConfig(source=intro_url, out_dir=tmp_path)

    root = write_structure_catalog(
        StructureRun(
            entries=[
                StructureEntry(
                    canonical_url=intro_url,
                    fetch_url=intro_url,
                    title="Introduction",
                    depth=0,
                    order=1,
                    nav_path=("Introduction",),
                ),
                StructureEntry(
                    canonical_url=change_url,
                    fetch_url=change_url,
                    title="Change List",
                    depth=1,
                    order=2,
                    nav_parent_url=intro_url,
                    nav_path=("Introduction", "Change List"),
                ),
                StructureEntry(
                    canonical_url=stable_url,
                    fetch_url=stable_url,
                    title="Stable",
                    depth=2,
                    order=3,
                    nav_parent_url=change_url,
                    nav_path=("Introduction", "Change List", "Stable"),
                ),
            ]
        ),
        config,
    )

    structure_text = (root / "_catalog" / "structure.yaml").read_text(encoding="utf-8")

    assert 'path: "docs/product_docs/content/introduction/_index.md"' in structure_text
    assert 'path: "docs/product_docs/content/introduction/change_list/_index.md"' in structure_text
    assert 'path: "docs/product_docs/content/introduction/change_list/stable-26/_index.md"' in structure_text

    write_mirror(
        [
            Page(
                source_url=change_url,
                canonical_url=change_url,
                title="Change List",
                markdown=f"[Stable]({stable_url})\n",
                depth=0,
                links_internal=[stable_url],
            )
        ],
        MirrorConfig(source=change_url, out_dir=tmp_path),
    )

    intro_path = root / "docs" / "product_docs" / "content" / "introduction" / "_index.md"
    change_path = root / "docs" / "product_docs" / "content" / "introduction" / "change_list" / "_index.md"
    stable_path = root / "docs" / "product_docs" / "content" / "introduction" / "change_list" / "stable-26" / "_index.md"
    pages_catalog = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")

    assert intro_path.exists()
    assert change_path.exists()
    assert stable_path.exists()
    assert 'page_type: "placeholder"' in intro_path.read_text(encoding="utf-8")
    assert 'page_type: "doc"' in change_path.read_text(encoding="utf-8")
    assert 'parent: "docs/product_docs/content/introduction/_index.md"' in change_path.read_text(encoding="utf-8")
    assert 'page_type: "placeholder"' in stable_path.read_text(encoding="utf-8")
    assert "[Stable](stable-26/_index.md)" in change_path.read_text(encoding="utf-8")
    assert 'path: "docs/product_docs/content/introduction/change_list/_index.md"' in pages_catalog
    assert not (root / "docs" / "product_docs" / "content" / "change_list" / "change_list.md").exists()


def test_writer_ignores_structure_paths_without_navigation_context(tmp_path: Path) -> None:
    source_url = "https://example.com/ru/advices"
    child_url = "https://example.com/ru/advices/work-on-tasks"
    config = MirrorConfig(source=source_url, out_dir=tmp_path)

    root = write_structure_catalog(
        StructureRun(
            entries=[
                StructureEntry(
                    canonical_url=source_url,
                    fetch_url=source_url,
                    title="Advices",
                    depth=0,
                    order=1,
                    path="t/index/index/advices-index/_index.md",
                ),
                StructureEntry(
                    canonical_url=child_url,
                    fetch_url=child_url,
                    title="Work On Tasks",
                    depth=1,
                    order=2,
                    nav_parent_url=source_url,
                    path="t/index/index/work-on-tasks-index/_index.md",
                ),
            ]
        ),
        config,
    )

    write_mirror(
        [
            Page(
                source_url=source_url,
                canonical_url=source_url,
                title="Advices",
                markdown=f"[Work]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Work On Tasks",
                markdown="Work content.\n",
                depth=1,
                nav_parent_url=source_url,
            ),
        ],
        config,
    )

    assert (root / "ru" / "advices" / "_index.md").exists()
    assert (root / "ru" / "advices" / "work-on-tasks" / "_index.md").exists()
    assert not (root / "t" / "index" / "index" / "advices-index" / "_index.md").exists()


def test_writer_ignores_incompatible_previous_catalog_path(tmp_path: Path) -> None:
    source_url = "https://example.com/ru/advices"
    child_url = "https://example.com/ru/advices/work-on-tasks"
    root = tmp_path / "example.com"
    catalog = root / "_catalog"
    catalog.mkdir(parents=True)
    (catalog / "pages.yaml").write_text(
        f'''pages:
  -
    path: "t/index/advices/_index.md"
    title: "Advices"
    source_url: "{source_url}"
    canonical_url: "{source_url}"
    nav_path: "[]"
    placeholder: false
  -
    path: "t/index/advices/work-on-tasks/_index.md"
    title: "Work"
    source_url: "{child_url}"
    canonical_url: "{child_url}"
    nav_path: "[]"
    placeholder: false
''',
        encoding="utf-8",
    )

    write_mirror(
        [
            Page(
                source_url=source_url,
                canonical_url=source_url,
                title="Advices",
                markdown=f"[Work]({child_url})\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Work",
                markdown="Work content.\n",
                depth=1,
                nav_parent_url=source_url,
            ),
        ],
        MirrorConfig(source=source_url, out_dir=tmp_path),
    )

    pages_catalog = (catalog / "pages.yaml").read_text(encoding="utf-8")

    assert (root / "ru" / "advices" / "_index.md").exists()
    assert (root / "ru" / "advices" / "work-on-tasks" / "_index.md").exists()
    assert 'path: "ru/advices/_index.md"' in pages_catalog
    assert 'path: "ru/advices/work-on-tasks/_index.md"' in pages_catalog
    assert 'path: "t/index/advices/_index.md"' not in pages_catalog


def test_writer_rewrites_missing_language_prefix_links(tmp_path: Path) -> None:
    source_url = "https://example.com/ru/advices"
    child_url = "https://example.com/ru/advices/work-on-tasks"

    root = write_mirror(
        [
            Page(
                source_url=source_url,
                canonical_url=source_url,
                title="Advices",
                markdown="[Work](https://example.com/advices/work-on-tasks)\n",
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url="https://example.com/advices/work-on-tasks",
                canonical_url=child_url,
                title="Work",
                markdown="Work content.\n",
                depth=1,
                nav_parent_url=source_url,
            ),
        ],
        MirrorConfig(source=source_url, out_dir=tmp_path),
    )

    text = (root / "ru" / "advices" / "_index.md").read_text(encoding="utf-8")

    assert "[Work](work-on-tasks/_index.md)" in text
    assert "https://example.com/advices/work-on-tasks" not in text


def test_writer_does_not_replace_existing_doc_with_structure_placeholder(tmp_path: Path) -> None:
    quick_url = "https://example.com/docs/product_docs/Content/QuickSolutions/Quick_solutions.htm"
    quick_fetch_url = quick_url + "?tocpath=_____7"
    other_url = "https://example.com/docs/product_docs/Content/Other/Other.htm"
    other_fetch_url = other_url + "?tocpath=_____8"
    config = MirrorConfig(source=quick_url, out_dir=tmp_path)

    root = write_structure_catalog(
        StructureRun(
            entries=[
                StructureEntry(
                    canonical_url=quick_url,
                    fetch_url=quick_fetch_url,
                    title="Quick Solutions",
                    depth=0,
                    order=1,
                    nav_path=("Quick Solutions",),
                ),
                StructureEntry(
                    canonical_url=other_url,
                    fetch_url=other_fetch_url,
                    title="Other",
                    depth=0,
                    order=2,
                    nav_path=("Other",),
                ),
            ]
        ),
        config,
    )

    write_mirror(
        [
            Page(
                source_url=quick_fetch_url,
                canonical_url=quick_url,
                title="Quick Solutions",
                markdown="Real quick solutions content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=quick_url, out_dir=tmp_path),
    )
    quick_path = root / "docs" / "product_docs" / "content" / "quicksolutions" / "quick_solutions" / "_index.md"

    assert 'page_type: "doc"' in quick_path.read_text(encoding="utf-8")
    assert "Real quick solutions content." in quick_path.read_text(encoding="utf-8")

    write_mirror(
        [
            Page(
                source_url=other_fetch_url,
                canonical_url=other_url,
                title="Other",
                markdown="Other content.\n",
                depth=0,
            )
        ],
        MirrorConfig(source=other_url, out_dir=tmp_path),
    )

    quick_text = quick_path.read_text(encoding="utf-8")
    pages_catalog = (root / "_catalog" / "pages.yaml").read_text(encoding="utf-8")

    assert 'page_type: "doc"' in quick_text
    assert "Real quick solutions content." in quick_text
    assert "Раздел ожидает отдельного зеркалирования" not in quick_text
    assert 'path: "docs/product_docs/content/quicksolutions/quick_solutions/_index.md"' in pages_catalog
    assert 'placeholder: false' in pages_catalog


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


def test_writer_drops_leading_heading_anchor_links_after_rewrite(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/plan.htm"
    page = Page(
        source_url=page_url,
        canonical_url=page_url,
        title="Plan",
        markdown=(
            "[Введение Example Product Docs](../_index.md) > План развития продукта\n"
            "# План развития продукта\n"
            "### Q4 - 2026\n"
            "[Q4 - 2026](#Q3_26) [Q3 - 2026](#Q2_26)\n"
            "[Q2 - 2026](#Q1_26) [Q1 - 2026](#legacy_unknown)\n\n"
            "  * Обновленные модули.\n"
        ),
        depth=0,
        anchor_headings={
            "Q3_26": "Q3 - 2026",
            "Q2_26": "Q2 - 2026",
            "Q1_26": "Q1 - 2026",
            "Q1_26_alt": "Q1 - 2026",
        },
    )

    root = write_mirror([page], MirrorConfig(source=page_url, out_dir=tmp_path))
    text = (root / "docs" / "plan.md").read_text(encoding="utf-8")

    assert "[Q4 - 2026]" not in text
    assert "[Q3 - 2026]" not in text
    assert "[Введение Example Product Docs](../_index.md) > План развития продукта" in text
    assert "### Q4 - 2026\n\n  * Обновленные модули." in text


def test_writer_rewrites_html_table_links(tmp_path: Path) -> None:
    parent_url = "https://example.com/ru/wiki"
    child_url = "https://example.com/ru/wiki/child"
    root = write_mirror(
        [
            Page(
                source_url=parent_url,
                canonical_url=parent_url,
                title="Wiki",
                markdown='<table><tr><td><a href="https://example.com/ru/wiki/child">Child</a></td></tr></table>\n',
                depth=0,
                links_internal=[child_url],
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="Child",
                markdown="Child.\n",
                depth=1,
            ),
        ],
        MirrorConfig(source=parent_url, out_dir=tmp_path),
    )

    text = (root / "ru" / "wiki" / "_index.md").read_text(encoding="utf-8")

    assert '<a href="child/_index.md">Child</a>' in text


def test_writer_creates_gramax_doc_root_next_to_content_folder(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/product_docs/Content/page.htm"
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

    doc_root = root / "docs" / "product_docs" / ".doc-root.yaml"

    assert doc_root.read_text(encoding="utf-8") == (
        "title: product_docs\n"
        "syntax: XML\n"
        "supportedLanguages: []\n"
        "properties: []\n"
    )


def test_writer_does_not_overwrite_existing_doc_root(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/product_docs/Content/page.htm"
    doc_root = tmp_path / "example.com" / "docs" / "product_docs" / ".doc-root.yaml"
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
