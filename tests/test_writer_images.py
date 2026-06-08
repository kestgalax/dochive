from __future__ import annotations

from pathlib import Path

from dochive.models import Asset, MirrorConfig, Page
from dochive.writer import (
    _is_inline_icon_asset,
    _isolate_gramax_images,
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


def test_isolate_gramax_images_splits_empty_bullet_image_and_text() -> None:
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
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert lines[1] == ""
    assert lines[2] == '<image src="./31.png" crop="0,0,100,100" width="25px" height="20px" float="left"/>'
    assert lines[3] == ""
    assert lines[4] == "  * [Service request](req.htm) (SR) – definition text."
    assert "scale=" not in isolated


def test_isolate_gramax_images_splits_merged_list_item() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = (
        '  * <image src="./31.png" crop="0,0,100,100" scale="100" width="25px" height="20px" '
        'float="left"/> [Service request](req.htm) (SR) – definition text.'
    )
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert lines[0] == ""
    assert lines[1].endswith('float="left"/>')
    assert lines[2] == ""
    assert lines[3] == "  * [Service request](req.htm) (SR) – definition text."


def test_isolate_gramax_images_splits_bullet_icon_and_continuation_text() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = "\n".join(
        [
            "  * ",
            '<image src="./32.png" crop="0,0,100,100" scale="100" width="19px" height="20px" float="center"/>',
            "",
            "Mass request definition text.",
        ]
    )
    isolated = _isolate_gramax_images(markdown, config)
    assert isolated.splitlines()[-1] == "  * Mass request definition text."


def test_isolate_clock_icon_list_case() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    green = (
        '<image src="./clockGreen_20x20-53aee3b47f5c.png" crop="0,0,100,100" '
        'width="20px" height="20px" float="left"/>'
    )
    red = (
        '<image src="./clockRed_20x20-5790b47e6e62.png" crop="0,0,100,100" '
        'width="20px" height="20px" float="left"/>'
    )
    markdown = "\n".join(
        [
            "Возможные значения:",
            f"    * {green}",
            "  – есть время на реакцию;",
            f"    * {red}",
            "  – нет времени на реакцию;",
        ]
    )
    isolated = _isolate_gramax_images(markdown, config)
    assert f"* {green}" not in isolated
    assert green in isolated
    assert red in isolated
    assert "  * – есть время на реакцию;" in isolated
    assert "  * – нет времени на реакцию;" in isolated
    assert isolated.index(green) < isolated.index("  * – есть время на реакцию;")
    assert isolated.index(red) < isolated.index("  * – нет времени на реакцию;")


def test_is_inline_icon_asset_respects_threshold() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"), image_inline_max_px=48)
    assert _is_inline_icon_asset(Asset("https://example.com/a.png", "images", width=25, height=20), config)
    assert not _is_inline_icon_asset(Asset("https://example.com/b.png", "images", width=120, height=80), config)
    assert not _is_inline_icon_asset(Asset("https://example.com/c.png", "images", width=50, height=20), config)

    default = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    assert _is_inline_icon_asset(Asset("https://example.com/c.png", "images", width=50, height=20), default)

    disabled = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"), image_inline_max_px=None)
    assert not _is_inline_icon_asset(Asset("https://example.com/a.png", "images", width=25, height=20), disabled)


def test_isolate_gramax_images_splits_icon_in_sentence() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    image_tag = (
        '<image src="./lm_p_01_31x30-e324f20148bc.png" crop="0,0,100,100" '
        'width="31px" height="30px" float="left"/>'
    )
    markdown = f"При нажатии на плитку {image_tag} на панели быстрого доступа, отображаются все разделы."
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert lines == [
        "При нажатии на плитку",
        "",
        image_tag,
        "",
        "на панели быстрого доступа, отображаются все разделы.",
    ]


def test_isolate_gramax_images_splits_single_icon_bullet_line() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = '  * <image src="./31.png" crop="0,0,100,100" width="25px" height="20px" float="left"/> '
    isolated = _isolate_gramax_images(markdown, config)
    assert isolated.startswith("\n")
    assert isolated.strip().endswith('float="left"/>')
    assert "* <image" not in isolated


def test_isolate_list_item_with_multiple_icons() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    img06 = '<image src="./06.png" crop="0,0,100,100" width="27px" height="20px" float="left"/>'
    img07 = '<image src="./07.png" crop="0,0,100,100" width="16px" height="20px" float="left"/>'
    img08 = '<image src="./08.png" crop="0,0,100,100" width="18px" height="20px" float="left"/>'
    markdown = f"  * {img06} {img07} {img08} Объект управления – текст."
    isolated = _isolate_gramax_images(markdown, config)
    assert img06 in isolated
    assert img07 in isolated
    assert img08 in isolated
    assert "  * Объект управления – текст." in isolated
    assert f"* {img06}" not in isolated


def test_isolate_list_continuation_with_icon_and_text() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    img07 = '<image src="./07.png" crop="0,0,100,100" width="16px" height="20px" float="left"/>'
    img08 = '<image src="./08.png" crop="0,0,100,100" width="18px" height="20px" float="left"/>'
    markdown = f"  {img07} {img08} Объект управления – текст."
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert img07 in lines
    assert img08 in lines
    assert "  Объект управления – текст." in lines


def test_isolate_handles_50px_icon_after_empty_list_marker() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    markdown = "\n".join(
        [
            "  * ",
            "",
            '<image src="./05.png" crop="0,0,100,100" scale="100" width="50px" height="20px" float="center"/>',
            "",
            "Правило – элемент настройки услуг.",
        ]
    )
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert lines[1] == '<image src="./05.png" crop="0,0,100,100" width="50px" height="20px" float="left"/>'
    assert lines[3] == "  * Правило – элемент настройки услуг."
    assert "scale=" not in isolated
    assert 'float="center"' not in isolated


def test_isolate_gramax_images_handles_multiple_icons_in_paragraph() -> None:
    config = MirrorConfig(source="https://example.com/", out_dir=Path("mirror"))
    first = '<image src="./a.png" width="25px" height="20px" float="left"/>'
    second = '<image src="./b.png" width="24px" height="20px" float="left"/>'
    markdown = f"Текст1 {first} текст2 {second} текст3"
    isolated = _isolate_gramax_images(markdown, config)
    lines = isolated.splitlines()
    assert lines == [
        "Текст1",
        "",
        first,
        "",
        "текст2",
        "",
        second,
        "",
        "текст3",
    ]


def test_write_mirror_splits_paragraph_icons(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/page.htm"
    icon = Asset(
        source="https://example.com/docs/lm_p_01.png",
        kind="images",
        local_path="docs/page/lm_p_01.png",
        width=31,
        height=30,
    )
    markdown = (
        "При нажатии на плитку "
        "![tile](https://example.com/docs/lm_p_01.png) "
        "на панели быстрого доступа, отображаются все разделы."
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
    assert "При нажатии на плитку\n\n<image src=" in body
    assert 'float="left"/>\n\nна панели быстрого доступа' in body
    assert "![tile]" not in body


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
    assert '  * <image src="./icon.png"' not in body
    assert '<image src="./icon.png"' in body
    assert "  * [Service request](req.htm) (SR) – definition text." in body
    assert "scale=" not in body
    assert 'float="center"' not in body


def test_write_mirror_process_description_icons(tmp_path: Path) -> None:
    page_url = "https://example.com/docs/process_description.htm"
    icons = [
        Asset(
            source=f"https://example.com/docs/{name}.png",
            kind="images",
            local_path=f"docs/process_description/{name}.png",
            width=width,
            height=height,
        )
        for name, width, height in [
            ("05_50x20", 50, 20),
            ("06_27x20", 27, 20),
            ("07_16x20", 16, 20),
            ("08_18x20", 16, 20),
        ]
    ]
    markdown = "\n".join(
        [
            "  * ",
            "",
            "![rule](https://example.com/docs/05_50x20.png)",
            "",
            "Правило – элемент настройки услуг.",
            (
                "  * ![06](https://example.com/docs/06_27x20.png) "
                "![07](https://example.com/docs/07_16x20.png) "
                "![08](https://example.com/docs/08_18x20.png) "
                "Объект управления – процессная активность."
            ),
        ]
    )
    root = write_mirror(
        [
            Page(
                source_url=page_url,
                canonical_url=page_url,
                title="Process description",
                markdown=markdown,
                depth=0,
                assets=icons,
            )
        ],
        MirrorConfig(source=page_url, out_dir=tmp_path),
    )
    body = (root / "docs" / "process_description.md").read_text(encoding="utf-8").split("---", 2)[2]
    for line in body.splitlines():
        if "<image" not in line.lower():
            continue
        tag_end = line.lower().rfind("/>")
        assert tag_end != -1
        assert not line[tag_end + 2 :].strip(), f"text after image tag: {line!r}"
    assert "  * <image src=" not in body
    assert "  * Правило – элемент настройки услуг." in body
    assert "  * Объект управления – процессная активность." in body
    assert 'float="center"' not in body
