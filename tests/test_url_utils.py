from dochive.web_source import _nav_path_points_to_current_page
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


def test_navigation_prefix_match_identifies_parent_for_nested_tocpath() -> None:
    assert _nav_path_points_to_current_page(
        ("Quick Start NSD Pro",),
        "Quick Start NSDPro - Naumen SD Pro",
    )
    assert not _nav_path_points_to_current_page(
        ("Quick Start NSD Pro", "Step 6"),
        "Quick Start NSDPro - Naumen SD Pro",
    )
