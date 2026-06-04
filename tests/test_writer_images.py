from __future__ import annotations

from pathlib import Path

from dochive.models import Asset, MirrorConfig, Page
from dochive.writer import (
    _collapse_inline_icon_images,
    _is_inline_icon_asset,
    _render_image,
    write_mirror,
)


def test_render_image_keeps_small_icons_inline_without_scale() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    asset = Asset(
        source="https://example.com/icon.png",
        kind="images",
        width=25,
        height=20,
    )
    rendered = _render_image("./icon.png", "", asset, config)
    assert rendered.startswith('<image src="./icon.png"')
    assert 'crop="0,0,100,100"' in rendered
    assert 'width="25px"' in rendered
    assert 'height="20px"' in rendered
    assert 'float="left"' in rendered
    assert "scale=" not in rendered
    assert "float=\"center\"" not in rendered
    assert "\n\n" not in rendered


def test_render_image_keeps_large_images_as_blocks() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    asset = Asset(
        source="https://example.com/diagram.png",
        kind="images",
        width=900,
        height=400,
    )
    rendered = _render_image("./diagram.png", "", asset, config)
    assert rendered.startswith("\n\n<image")
    assert 'float="center"' in rendered
    assert 'scale="100"' in rendered


def test_collapse_inline_icon_images_splits_image_and_text_lines() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = "\n".join(
        [
            "### Objects",
            "  * ",
            '<image src="./31.png" crop="0,0,100,100" scale="100" width="25px" height="20px" float="center"/>',
            "",
            " [Service request](req.htm) (SR) – definition text.",
        ]
    )
    collapsed = _collapse_inline_icon_images(markdown, config)
    lines = collapsed.splitlines()
    assert lines[1] == '  * <image src="./31.png" crop="0,0,100,100" width="25px" height="20px" float="left"/> '
    assert lines[2] == " [Service request](req.htm) (SR) – definition text."
    assert "scale=" not in collapsed


def test_collapse_inline_icon_images_splits_already_merged_list_items() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = (
        '  * <image src="./31.png" crop="0,0,100,100" scale="100" width="25px" height="20px" '
        'float="left"/> [Service request](req.htm) (SR) – definition text.'
    )
    collapsed = _collapse_inline_icon_images(markdown, config)
    lines = collapsed.splitlines()
    assert len(lines) == 2
    assert lines[0].endswith('float="left"/> ')
    assert lines[1].startswith(" [Service request]")


def test_collapse_inline_icon_images_indents_plain_text() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = "\n".join(
        [
            "  * ",
            '<image src="./32.png" crop="0,0,100,100" scale="100" width="19px" height="20px" float="center"/>',
            "",
            "Mass request definition text.",
        ]
    )
    collapsed = _collapse_inline_icon_images(markdown, config)
    assert collapsed.splitlines()[-1] == "  Mass request definition text."


def test_is_inline_icon_asset_respects_threshold() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"), image_inline_max_px=48)
    assert _is_inline_icon_asset(Asset("https://example.com/a.png", "images", width=25, height=20), config)
    assert not _is_inline_icon_asset(Asset("https://example.com/b.png", "images", width=120, height=80), config)

    disabled = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"), image_inline_max_px=None)
    assert not _is_inline_icon_asset(Asset("https://example.com/a.png", "images", width=25, height=20), disabled)


def test_write_mirror_formats_icon_images_for_gramax_lists(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/page.htm"
    icon = Asset(
        source="https://example.com/docs/icon.png",
        kind="images",
        local_path="docs/page/icon.png",
        width=25,
        height=20,
    )
    markdown = "\n".join(
        [
            "### Objects",
            "  * ",
            "",
            '<image src="./icon.png" crop="0,0,100,100" scale="100" width="25px" height="20px" float="center"/>',
            "",
            " [Service request](req.htm) (SR) – definition text.",
        ]
    )
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Page",
                markdown=markdown,
                depth=0,
                assets=[icon],
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )
    body = (root / "docs" / "page.md").read_text(encoding="utf-8").split("---", 2)[2]
    assert '  * <image src="./icon.png"' in body
    assert body.endswith('float="left"/> \n [Service request](req.htm) (SR) – definition text.\n') or (
        'float="left"/> ' in body and "\n [Service request]" in body
    )
    assert "scale=" not in body
    assert 'float="center"' not in body
