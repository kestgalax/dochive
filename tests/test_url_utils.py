import asyncio
from pathlib import Path

from dochive.models import MirrorConfig
from dochive.models import Page
from dochive.web_source import (
    _build_navigation_index,
    _nav_path_points_to_current_page,
    _navigation_entries_to_structure,
    _remember_navigation_hint,
    _structure_root_fetch_url,
)
from dochive.url_utils import canonicalize_url, extract_tocpath


class FakeCrawlResult:
    success = True

    def __init__(self, title: str, links: list[dict[str, str]]) -> None:
        self.metadata = {"title": title}
        self.links = {"internal": links}


class FakeCrawler:
    def __init__(self, pages: dict[str, FakeCrawlResult]) -> None:
        self.pages = pages

    async def arun(self, *, url: str, config: object) -> FakeCrawlResult:
        return self.pages[url]


def test_canonical_url_drops_tocpath_but_tocpath_can_be_extracted() -> None:
    url = (
        "https://www.naumen.ru/docs/sd/nsdpro/Content/spm/functionality.htm"
        "?tocpath=Practices%20NSD%20Pro%7CService%20Management%7C_____0"
    )

    assert canonicalize_url(url) == "https://www.naumen.ru/docs/sd/nsdpro/Content/spm/functionality.htm"
    assert extract_tocpath(url) == ("Practices NSD Pro", "Service Management")


def test_extract_tocpath_accepts_madcap_query_casing() -> None:
    url = "https://example.com/docs/step.htm?TocPath=Quick%20Start%7C_____1"

    assert extract_tocpath(url) == ("Quick Start",)


def test_structure_root_fetch_url_uses_madcap_main_page() -> None:
    source = (
        "https://www.naumen.ru/docs/sd/nsdpro/Content/introduction/introduction.htm"
        "?tocpath=Intro%7C_____0"
    )

    assert _structure_root_fetch_url(source) == "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm"


def test_structure_root_fetch_url_keeps_existing_main_page() -> None:
    source = "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm"

    assert _structure_root_fetch_url(source) == source


def test_navigation_label_match_ignores_site_suffix_and_spacing() -> None:
    assert _nav_path_points_to_current_page(("Quick Start NSD Pro",), "Quick Start NSDPro - Naumen SD Pro")


def test_navigation_label_match_supports_cyrillic_site_suffix() -> None:
    label = "\u041b\u0438\u0447\u043d\u044b\u0439 \u043f\u0440\u043e\u0444\u0438\u043b\u044c \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u0430"
    title = f"{label} \u2013 Naumen SD Pro"

    assert _nav_path_points_to_current_page((label,), title)


def test_navigation_prefix_match_identifies_parent_for_nested_tocpath() -> None:
    assert _nav_path_points_to_current_page(
        ("Quick Start NSD Pro",),
        "Quick Start NSDPro - Naumen SD Pro",
    )
    assert not _nav_path_points_to_current_page(
        ("Quick Start NSD Pro", "Step 6"),
        "Quick Start NSDPro - Naumen SD Pro",
    )


def test_navigation_hint_with_tocpath_upgrades_already_seen_page() -> None:
    parent_url = "https://example.com/docs/QuickStartSDPro/LK_int_vkl.htm"
    target_url = "https://example.com/docs/QuickStartSDPro/LK_dispositionChange.htm"
    target_fetch_url = (
        "https://example.com/docs/QuickStartSDPro/LK_dispositionChange.htm"
        "?tocpath=Quick%20Start%7CStep%206%7CWork%20interface%7CPersonal%20profile%7C_____2"
    )
    target_page = Page(
        source_url=target_url,
        canonical_url=target_url,
        title="Disposition change",
        markdown="Disposition change.\n",
        depth=2,
        parent_url="https://example.com/docs/QuickStartSDPro/work_interface.htm",
    )
    fetch_url_by_canonical = {target_url: target_url}
    nav_path_by_canonical: dict[str, tuple[str, ...]] = {}
    nav_parent_by_canonical: dict[str, str] = {}
    page_by_canonical = {target_url: target_page}

    _remember_navigation_hint(
        target_url,
        target_fetch_url=target_fetch_url,
        target_nav_path=("Quick Start", "Step 6", "Work interface", "Personal profile"),
        link_text="Disposition change",
        current_url=parent_url,
        current_title="Personal profile - Naumen SD Pro",
        fetch_url_by_canonical=fetch_url_by_canonical,
        nav_path_by_canonical=nav_path_by_canonical,
        nav_parent_by_canonical=nav_parent_by_canonical,
        page_by_canonical=page_by_canonical,
    )

    assert fetch_url_by_canonical[target_url] == target_fetch_url
    assert nav_parent_by_canonical[target_url] == parent_url
    assert nav_path_by_canonical[target_url] == (
        "Quick Start",
        "Step 6",
        "Work interface",
        "Personal profile",
        "Disposition change",
    )
    assert target_page.source_url == target_fetch_url
    assert target_page.nav_parent_url == parent_url
    assert target_page.nav_path == nav_path_by_canonical[target_url]


def test_navigation_hint_keeps_existing_path_but_upgrades_fetch_url() -> None:
    parent_url = "https://example.com/docs/parent.htm"
    target_url = "https://example.com/docs/child.htm"
    target_fetch_url = "https://example.com/docs/child.htm?tocpath=Root%7CParent%7CChild%7C_____0"
    existing_path = ("Root", "Parent", "Child")
    target_page = Page(
        source_url=target_url,
        canonical_url=target_url,
        title="Child",
        markdown="Child.\n",
        depth=2,
        nav_path=existing_path,
    )
    fetch_url_by_canonical = {target_url: target_url}
    nav_path_by_canonical = {target_url: existing_path}
    nav_parent_by_canonical: dict[str, str] = {}

    _remember_navigation_hint(
        target_url,
        target_fetch_url=target_fetch_url,
        target_nav_path=existing_path,
        link_text="Child",
        current_url=parent_url,
        current_title="Parent - Naumen SD Pro",
        fetch_url_by_canonical=fetch_url_by_canonical,
        nav_path_by_canonical=nav_path_by_canonical,
        nav_parent_by_canonical=nav_parent_by_canonical,
        page_by_canonical={target_url: target_page},
    )

    assert fetch_url_by_canonical[target_url] == target_fetch_url
    assert target_page.source_url == target_fetch_url
    assert target_page.nav_path == existing_path
    assert target_page.nav_parent_url == parent_url


def test_navigation_index_is_built_before_content_fetch_and_upgrades_plain_link() -> None:
    root_url = "https://example.com/docs/root.htm"
    parent_url = "https://example.com/docs/parent.htm"
    child_url = "https://example.com/docs/child.htm"
    parent_fetch_url = f"{parent_url}?tocpath=Root%7CParent%7C_____0"
    child_fetch_url = f"{child_url}?tocpath=Root%7CParent%7CChild%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Root - Naumen SD Pro",
                [
                    {"href": child_url, "text": "Child"},
                    {"href": parent_fetch_url, "text": "Parent"},
                ],
            ),
            child_url: FakeCrawlResult("Child - Naumen SD Pro", []),
            child_fetch_url: FakeCrawlResult("Child - Naumen SD Pro", []),
            parent_fetch_url: FakeCrawlResult("Parent - Naumen SD Pro", [{"href": child_fetch_url, "text": "Child"}]),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert entries[child_url].fetch_url == child_fetch_url
    assert entries[child_url].nav_parent_url == parent_url
    assert entries[child_url].nav_path == ("Root", "Parent", "Child")
    assert entries[child_url].depth == 2


def test_navigation_index_exports_structure_entries_with_titles() -> None:
    root_url = "https://example.com/docs/root.htm"
    child_url = "https://example.com/docs/child.htm"
    child_fetch_url = f"{child_url}?tocpath=Root%7CChild%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult("Root - Naumen SD Pro", [{"href": child_fetch_url, "text": "Child"}]),
            child_fetch_url: FakeCrawlResult("Child - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=("Root",),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    structure = _navigation_entries_to_structure(entries)

    assert issues == []
    assert structure[0].canonical_url == root_url
    assert structure[0].title == "Root"
    assert structure[1].canonical_url == child_url
    assert structure[1].fetch_url == child_fetch_url
    assert structure[1].title == "Child"
    assert structure[1].placeholder is True


def test_navigation_structure_skips_synthetic_main_page_root() -> None:
    root_url = "https://example.com/docs/main_page.htm"
    intro_url = "https://example.com/docs/intro.htm"
    intro_fetch_url = f"{intro_url}?tocpath=Intro%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult("Main - Naumen SD Pro", [{"href": intro_fetch_url, "text": "Intro"}]),
            intro_fetch_url: FakeCrawlResult("Intro - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    structure = _navigation_entries_to_structure(entries, root_url=root_url)

    assert issues == []
    assert [entry.canonical_url for entry in structure] == [intro_url]
    assert structure[0].nav_path == ("Intro",)


def test_navigation_structure_drops_synthetic_main_page_parent() -> None:
    root_url = "https://example.com/docs/main_page.htm"
    child_url = "https://example.com/docs/child.htm"
    child_fetch_url = f"{child_url}?tocpath=Child%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult("Main - Naumen SD Pro", [{"href": child_fetch_url, "text": "Child"}]),
            child_fetch_url: FakeCrawlResult("Child - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    entries[child_url].nav_parent_url = root_url
    structure = _navigation_entries_to_structure(entries, root_url=root_url)

    assert issues == []
    assert structure[0].canonical_url == child_url
    assert structure[0].nav_parent_url is None


def test_navigation_index_keeps_main_page_section_landings_top_level() -> None:
    root_url = "https://example.com/docs/main_page.htm"
    admin_url = "https://example.com/docs/admin_applied/admin_applied.htm"
    intro_url = "https://example.com/docs/introduction/introduction.htm"
    admin_fetch_url = f"{admin_url}?tocpath=Intro%7CAdmin%7C_____0"
    intro_fetch_url = f"{intro_url}?tocpath=Intro%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Main - Naumen SD Pro",
                [
                    {"href": admin_fetch_url, "text": "Admin"},
                    {"href": intro_fetch_url, "text": "Intro"},
                ],
            ),
            admin_fetch_url: FakeCrawlResult("Admin - Naumen SD Pro", []),
            intro_fetch_url: FakeCrawlResult("Intro - Naumen SD Pro", [{"href": admin_fetch_url, "text": "Admin"}]),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert entries[admin_url].nav_parent_url is None
    assert entries[admin_url].nav_path == ("Admin",)


def test_navigation_index_preserves_deep_tocpath_for_main_page_shortcuts() -> None:
    root_url = "https://example.com/docs/main_page.htm"
    portal_url = "https://example.com/docs/QuickStartSDPro/work_portal.htm"
    portal_fetch_url = f"{portal_url}?tocpath=Quick%20Start%7CStep%206%7CPortal%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult("Main - Naumen SD Pro", [{"href": portal_fetch_url, "text": "Portal"}]),
            portal_fetch_url: FakeCrawlResult("Portal - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert entries[portal_url].nav_parent_url is None
    assert entries[portal_url].nav_path == ("Quick Start", "Step 6", "Portal")


def test_navigation_index_ignores_non_html_page_targets() -> None:
    root_url = "https://example.com/docs/main_page.htm"
    image_url = "https://example.com/docs/Resources/Images/process_list.png"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult("Main - Naumen SD Pro", [{"href": image_url, "text": "Process List"}]),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert image_url not in entries


def test_navigation_index_prioritizes_tocpath_links_for_page_limit() -> None:
    root_url = "https://example.com/docs/root.htm"
    context_url = "https://example.com/docs/context.htm"
    nav_url = "https://example.com/docs/nav.htm"
    nav_fetch_url = f"{nav_url}?tocpath=Root%7CNav%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Root - Naumen SD Pro",
                [
                    {"href": context_url, "text": "Context"},
                    {"href": nav_fetch_url, "text": "Nav"},
                ],
            ),
            nav_fetch_url: FakeCrawlResult("Nav - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=2, max_pages=2),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert nav_url in entries
    assert entries[context_url].placeholder is True


def test_navigation_index_adds_plain_links_within_allowed_scope() -> None:
    root_url = "https://example.com/docs/root.htm"
    old_url = "https://example.com/docs/old.htm"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Root - Naumen SD Pro",
                [{"href": old_url, "text": "Old page"}],
            ),
            old_url: FakeCrawlResult("Old page - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=(),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert old_url in entries
    assert entries[old_url].fetch_url == old_url
    assert entries[old_url].depth == 1
    assert entries[old_url].nav_parent_url == root_url


def test_navigation_index_plain_link_inherits_parent_nav_path() -> None:
    root_url = "https://example.com/docs/root.htm"
    child_url = "https://example.com/docs/child.htm"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Root - Naumen SD Pro",
                [{"href": child_url, "text": "Child Page"}],
            ),
            child_url: FakeCrawlResult("Child page - Naumen SD Pro", []),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=("Root",),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert entries[child_url].nav_parent_url == root_url
    assert entries[child_url].nav_path == ("Root", "Child Page")


def test_navigation_index_self_link_does_not_change_root_depth() -> None:
    root_url = "https://example.com/docs/root.htm"
    root_fetch_url = f"{root_url}?tocpath=Root%7CSection%7C_____0"
    crawler = FakeCrawler(
        {
            root_fetch_url: FakeCrawlResult(
                "Section - Naumen SD Pro",
                [{"href": root_fetch_url, "text": "Section"}],
            ),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_fetch_url, out_dir=Path("."), max_depth=5, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_fetch_url,
            root_nav_path=("Root", "Section"),
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert entries[root_url].depth == 0


def test_navigation_index_creates_placeholder_for_nav_link_outside_scope() -> None:
    root_url = "https://example.com/docs/intro/intro.htm"
    change_url = "https://example.com/docs/Change_List/Change_List.htm"
    main_url = "https://example.com/docs/main_page.htm"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Introduction - Naumen SD Pro",
                [
                    {"href": change_url, "text": "Change List"},
                    {"href": main_url, "text": "Main"},
                    {"href": "https://cdn.example.net/image.png", "text": "Image"},
                ],
            ),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=("Introduction",),
            allowed_prefixes=("https://example.com/docs/intro/",),
        )
    )

    assert issues == []
    assert entries[change_url].placeholder is True
    assert entries[change_url].nav_path == ("Introduction", "Change List")
    assert entries[change_url].nav_parent_url is None
    assert main_url not in entries


def test_navigation_index_plain_context_placeholder_uses_url_section_not_current_page() -> None:
    root_url = "https://example.com/docs/Change_List/archive.htm"
    target_url = "https://example.com/docs/spm_role/service_category_owner.htm"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Archive - Naumen SD Pro",
                [{"href": target_url, "text": "подробнее"}],
            ),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=("Introduction", "Change List", "Archive"),
            allowed_prefixes=("https://example.com/docs/Change_List/",),
        )
    )

    assert issues == []
    assert entries[target_url].placeholder is True
    assert entries[target_url].nav_path == ("Introduction", "Change List", "Archive", "Service Category Owner")
    assert entries[target_url].nav_parent_url is None


def test_navigation_index_does_not_nest_placeholder_with_independent_tocpath() -> None:
    root_url = "https://example.com/docs/intro/intro.htm"
    quick_url = "https://example.com/docs/quick/quick.htm"
    quick_fetch_url = f"{quick_url}?tocpath=Quick%20Start%7C_____0"
    crawler = FakeCrawler(
        {
            root_url: FakeCrawlResult(
                "Introduction - Naumen SD Pro",
                [{"href": quick_fetch_url, "text": "Quick Start"}],
            ),
        }
    )

    entries, issues = asyncio.run(
        _build_navigation_index(
            crawler,
            object(),
            MirrorConfig(source=root_url, out_dir=Path("."), max_depth=3, max_pages=10),
            root_url=root_url,
            root_fetch_url=root_url,
            root_nav_path=("Introduction",),
            allowed_prefixes=("https://example.com/docs/intro/",),
        )
    )

    assert issues == []
    assert entries[quick_url].placeholder is True
    assert entries[quick_url].nav_path == ("Quick Start",)
    assert entries[quick_url].nav_parent_url is None
