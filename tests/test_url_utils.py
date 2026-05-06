import asyncio
from pathlib import Path

from dochive.madcap_toc import (
    build_toc_nodes,
    help_system_toc_path,
    parse_toc_chunk_js,
    parse_toc_js,
    select_toc_roots,
    toc_nodes_to_structure_entries,
)
from dochive.models import MirrorConfig
from dochive.models import Page
from dochive.models import StructureEntry
from dochive.web_source import (
    _build_navigation_index,
    _fetch_pages_from_structure_entries,
    _nav_path_points_to_current_page,
    _navigation_entries_to_structure,
    _remember_navigation_hint,
    _structure_root_fetch_url,
)
from dochive.url_utils import canonicalize_url, extract_tocpath
from dochive.writer import write_mirror


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


HELP_SYSTEM_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<WebHelpSystem DefaultUrl="Content/main_page.htm" Toc="Data/Tocs/TOC_CORP_manual.js" />
"""


def _madcap_intro_tree_js() -> str:
    return """\
define({numchunks:1,prefix:'TOC_CORP_manual_Chunk',tree:{n:[
{i:0,c:0,n:[{i:1,c:0},{i:2,c:0,n:[{i:3,c:0},{i:4,c:0,n:[
{i:5,c:0},{i:6,c:0},{i:7,c:0},{i:8,c:0},{i:9,c:0},{i:10,c:0},{i:11,c:0},{i:12,c:0},{i:13,c:0}
]}]},{i:14,c:0}]},
{i:15,c:0}
]}});"""


def _madcap_intro_chunk_js() -> str:
    return """\
define({
'/Content/introduction/introduction.htm':{i:[0],t:['Введение Naumen\\u00a0Service\\u00a0Desk\\u00a0Pro'],b:['']},
'/Content/introduction/plan.htm':{i:[1],t:['План развития продукта'],b:['']},
'/Content/Change_List/Change_List.htm':{i:[2],t:['Описание изменений'],b:['']},
'/Content/Change_List/stable-26.htm':{i:[3],t:['Стабильная версия stable-26-4'],b:['']},
'/Content/Change_List/Change_List_arch.htm':{i:[4],t:['Архив описания изменений'],b:['']},
'/Content/Change_List/Change_List_30_video.htm':{i:[5],t:['Архив описания изменений. Видео инструкции 3.0'],b:['']},
'/Content/Change_List/beta_35.htm':{i:[6],t:['Архив описания изменений 3.5'],b:['']},
'/Content/Change_List/Change_List_arch_3.3.htm':{i:[7],t:['Архив описания изменений 3.3'],b:['']},
'/Content/Change_List/Change_List_beta.htm':{i:[8],t:['Архив описания изменений  3.0'],b:['']},
'/Content/Change_List/Change_List_stable28.htm':{i:[9],t:['Архив описания изменений 2.8'],b:['']},
'/Content/Change_List/Change_List_arch_281.htm':{i:[10],t:['Архив описания изменений 2.8.1'],b:['']},
'/Content/Change_List/Change_List_arch_2713.htm':{i:[11],t:['Архив описания изменений 2.7.13'],b:['']},
'/Content/Change_List/Change_List_arch_2712.htm':{i:[12],t:['Архив изменений 2.7.12'],b:['']},
'/Content/Change_List/Change_List_arch_2711_268.htm':{i:[13],t:['Архив изменений 2.7.11 - 2.6.8'],b:['']},
'/Content/introduction/glossary.htm':{i:[14],t:['Глоссарий терминов'],b:['']},
'/Content/QuickStartSDPro/QuickStartSDPro.htm':{i:[15],t:['Быстрый старт NSD\\u00a0Pro'],b:['']}
});"""


def _madcap_toc_roots():
    toc = parse_toc_js(_madcap_intro_tree_js())
    metadata = parse_toc_chunk_js(_madcap_intro_chunk_js())
    return build_toc_nodes(toc["tree"], metadata)


def test_help_system_toc_path_reads_madcap_toc_attribute() -> None:
    assert help_system_toc_path(HELP_SYSTEM_XML) == "Data/Tocs/TOC_CORP_manual.js"


def test_madcap_toc_source_url_selects_exact_subtree() -> None:
    selected = select_toc_roots(
        _madcap_toc_roots(),
        "https://www.naumen.ru/docs/sd/nsdpro/Content/introduction/introduction.htm"
        "?tocpath=%D0%92%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5%7C_____0",
        root_url="https://www.naumen.ru/docs/sd/nsdpro/",
        scope="subtree",
    )
    entries = toc_nodes_to_structure_entries(selected, root_url="https://www.naumen.ru/docs/sd/nsdpro/")

    assert len(entries) == 15
    assert entries[0].title == "Введение Naumen Service Desk Pro"
    assert entries[0].depth == 0
    assert entries[1].nav_parent_url == entries[0].canonical_url
    assert entries[-1].nav_path == ("Введение Naumen Service Desk Pro", "Глоссарий терминов")


def test_madcap_main_page_uses_full_toc_and_home_tile_does_not_reparent_change_list() -> None:
    selected = select_toc_roots(
        _madcap_toc_roots(),
        "https://www.naumen.ru/docs/sd/nsdpro/Content/main_page.htm",
        root_url="https://www.naumen.ru/docs/sd/nsdpro/",
        scope="subtree",
    )
    entries = toc_nodes_to_structure_entries(selected, root_url="https://www.naumen.ru/docs/sd/nsdpro/")
    change_entry = next(entry for entry in entries if entry.title == "Описание изменений")

    assert len(entries) == 16
    assert [entry.title for entry in entries if entry.depth == 0] == [
        "Введение Naumen Service Desk Pro",
        "Быстрый старт NSD Pro",
    ]
    assert change_entry.nav_path == ("Введение Naumen Service Desk Pro", "Описание изменений")


def test_madcap_full_toc_can_reconstruct_large_tree() -> None:
    node_count = 1666
    tree_js = "define({numchunks:1,prefix:'Chunk',tree:{n:[" + ",".join(
        f"{{i:{index},c:0}}" for index in range(node_count)
    ) + "]}});"
    chunk_js = "define({" + ",".join(
        f"'/Content/page{index}.htm':{{i:[{index}],t:['Page {index}'],b:['']}}"
        for index in range(node_count)
    ) + "});"
    toc = parse_toc_js(tree_js)
    roots = build_toc_nodes(toc["tree"], parse_toc_chunk_js(chunk_js))

    assert len(toc_nodes_to_structure_entries(roots, root_url="https://example.com/docs/")) == 1666


class StructureFakeCrawlResult:
    success = True
    status_code = 200
    media = {}

    def __init__(self, title: str, links: list[dict[str, str]]) -> None:
        self.metadata = {"title": title, "description": ""}
        self.links = {"internal": links, "external": []}
        self.markdown = f"# {title}\n\nBody.\n"
        self.html = f"<h1>{title}</h1><p>Body.</p>"


class StructureFakeCrawler:
    async def arun(self, *, url: str, config: object) -> StructureFakeCrawlResult:
        return StructureFakeCrawlResult(
            "Intro",
            [{"href": "https://example.com/docs/off-branch.htm", "text": "Off branch"}],
        )


def test_toc_mirror_queue_does_not_add_off_branch_links() -> None:
    entries = [
        StructureEntry(
            canonical_url="https://example.com/docs/intro.htm",
            fetch_url="https://example.com/docs/intro.htm",
            title="Intro",
            depth=0,
            order=1,
            nav_path=("Intro",),
        )
    ]

    pages, issues = asyncio.run(
        _fetch_pages_from_structure_entries(
            StructureFakeCrawler(),
            object(),
            MirrorConfig(source="https://example.com/docs/intro.htm", out_dir=Path("."), structure_mode="toc"),
            entries,
            root_url="https://example.com/docs/intro.htm",
            allowed_prefixes=("https://example.com/docs/",),
        )
    )

    assert issues == []
    assert [page.canonical_url for page in pages] == ["https://example.com/docs/intro.htm"]


def test_folder_indexes_use_toc_titles_for_child_folders(tmp_path: Path) -> None:
    root_url = "https://example.com/docs/QuickStartSDPro/QuickStartSDPro.htm"
    child_url = "https://example.com/docs/QuickStartSDPro/1.htm"
    root = write_mirror(
        [
            Page(
                source_url=root_url,
                canonical_url=root_url,
                title="Быстрый старт NSD Pro",
                markdown="# Быстрый старт NSD Pro\n",
                depth=0,
                nav_path=("Быстрый старт NSD Pro",),
            ),
            Page(
                source_url=child_url,
                canonical_url=child_url,
                title="ШАГ1 Определение участников ключевых ролей",
                markdown="# ШАГ1 Определение участников ключевых ролей\n",
                depth=1,
                nav_parent_url=root_url,
                nav_path=("Быстрый старт NSD Pro", "ШАГ1 Определение участников ключевых ролей"),
            ),
        ],
        MirrorConfig(source=root_url, out_dir=tmp_path),
    )

    content_index = (root / "docs" / "_index.yaml").read_text(encoding="utf-8")
    quickstart_index = (root / "docs" / "quickstartsdpro" / "_index.yaml").read_text(encoding="utf-8")
    assert 'title: "Быстрый старт NSD Pro"' in content_index
    assert 'title: "Быстрый старт NSD Pro"' in quickstart_index
