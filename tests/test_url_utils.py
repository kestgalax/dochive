from dochive.models import Page
from dochive.web_source import _nav_path_points_to_current_page, _remember_navigation_hint
from dochive.url_utils import canonicalize_url, extract_tocpath


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
