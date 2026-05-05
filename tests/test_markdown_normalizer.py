from dochive.markdown_normalizer import normalize_markdown
from dochive.html_extract import promote_markdown_headings


def test_separates_media_tags_with_blank_lines() -> None:
    markdown = """
Before.
<video path="./demo.mp4"/>
After.
<image src="./demo.png" float="center"/>
Done.
"""

    assert normalize_markdown(markdown) == """Before.

<video path="./demo.mp4"/>

After.

<image src="./demo.png" float="center"/>

Done.
"""


def test_drops_copy_link_before_fenced_code() -> None:
    markdown = """
[Copy](./change_list_arch_281)

```
"userCatalog" : [
"uuid" : "analyticalCat$38378701",
]
```
"""

    assert normalize_markdown(markdown) == '''```
"userCatalog" : [
"uuid" : "analyticalCat$38378701",
]
```
'''


def test_keeps_regular_copy_link_away_from_code() -> None:
    markdown = """
See [Copy](./copy-page) for details.

Regular paragraph.
"""

    assert normalize_markdown(markdown) == "See [Copy](./copy-page) for details.\n\nRegular paragraph.\n"


def test_fences_raw_html_examples() -> None:
    markdown = """
Before.

<strong>Article table of contents</strong>

<a href="#label1">Link to label1</a>

<br>

<a name="label1"></a>

<h2>Section heading 1</h2>

After.
"""

    assert normalize_markdown(markdown) == """Before.

```html
<strong>Article table of contents</strong>

<a href="#label1">Link to label1</a>

<br>

<a name="label1"></a>

<h2>Section heading 1</h2>
```
After.
"""


def test_drops_next_page_navigation_links() -> None:
    markdown = """
Content.

**\u0414\u0430\u043b\u0435\u0435 >> ** [Step 2](2.md)

More content.
"""

    assert normalize_markdown(markdown) == "Content.\n\nMore content.\n"


def test_drops_leading_heading_anchor_buttons() -> None:
    markdown = """
[Q4 - 2026](#Q4_26)

### Q4 - 2026
Release notes.
"""

    assert (
        normalize_markdown(markdown, anchor_headings={"Q4_26": "Q4 - 2026"})
        == "### Q4 - 2026\nRelease notes.\n"
    )


def test_drops_leading_heading_anchor_toc_after_title() -> None:
    markdown = """
# Лицензии

- [Пользовательские лицензии](#1)
- [Лицензионный файл](#2)
- [Учет сессий](#3)
- [Контроль используемых лицензий](#4)

## Пользовательские лицензии
Основной текст.
"""

    assert normalize_markdown(
        markdown,
        anchor_headings={
            "1": "Пользовательские лицензии",
            "2": "Лицензионный файл",
            "3": "Учет сессий",
            "4": "Контроль используемых лицензий",
        },
    ) == "# Лицензии\n\n## Пользовательские лицензии\nОсновной текст.\n"


def test_drops_leading_links_rewritten_to_heading_anchor_text() -> None:
    markdown = """
# План развития продукта
### Q4 - 2026
[Q4 - 2026](#Q3 - 2026) [Q3 - 2026](#Q2 - 2026) [Q2 - 2026](#Q1 - 2026)
[Q1 - 2026](#Q4 - 2025) [Q4 - 2025](#Q3_25)

  * Обновленные модули.
"""

    assert normalize_markdown(
        markdown,
        anchor_headings={
            "Q3_26": "Q3 - 2026",
            "Q2_26": "Q2 - 2026",
            "Q1_26": "Q1 - 2026",
            "Q4_25": "Q4 - 2025",
            "Q3_25": "Q3 - 2025",
        },
    ) == "# План развития продукта\n### Q4 - 2026\n\n  * Обновленные модули.\n"


def test_keeps_body_heading_anchor_links() -> None:
    markdown = """
# Лицензии

В этом разделе см. [Лицензионный файл](#2).

## Лицензионный файл
Основной текст.
"""

    assert normalize_markdown(markdown, anchor_headings={"2": "Лицензионный файл"}) == (
        "# Лицензии\n\n"
        "В этом разделе см. [Лицензионный файл](#2).\n\n"
        "## Лицензионный файл\n"
        "Основной текст.\n"
    )


def test_cleanup_rules_ignore_fenced_code() -> None:
    markdown = """
```html
<strong>Article table of contents</strong>
<a href="#label1">Link to label1</a>
**\u0414\u0430\u043b\u0435\u0435 >> ** [Step 2](2.md)
```
"""

    assert normalize_markdown(markdown) == """```html
<strong>Article table of contents</strong>
<a href="#label1">Link to label1</a>
**\u0414\u0430\u043b\u0435\u0435 >> ** [Step 2](2.md)
```
"""


def test_drops_embedded_madcap_navigation_before_real_article() -> None:
    markdown = """
# Helpful Functions
  * [Files](file.md)
  * [Search](search.md)
  * [Lists](lists.md)
  * [Forms](forms.md)
  * [Favorites](favorites.md)

[Skip To Main Content](#mc-main-content)

<image src="./transparent.gif"/>

  * [Intro](intro.md)
  * [Quick Start](quick.md)
    * [Step 1](1.md)
    * [Step 2](2.md)

[Quick Start](../../_index.md) > Helpful Functions
# Helpful Functions
Actual article text.
"""

    assert normalize_markdown(markdown) == """[Quick Start](../../_index.md) > Helpful Functions
# Helpful Functions
Actual article text.
"""


def test_promote_markdown_headings_drops_later_duplicate_after_anchor_insertion() -> None:
    html = """
<p class="H3"><a name="Q4_22"></a>Q4 - 2022</p>
<ul><li>First item.</li></ul>
"""
    markdown = """
First item.

### Q4 - 2022
"""

    assert promote_markdown_headings(markdown, html).count("### Q4 - 2022") == 1


def test_promote_markdown_headings_does_not_use_body_text_as_anchor_hint() -> None:
    html = """
<p class="H3"><a name="Q1"></a>Q1 - 2023</p>
<p>Common label:</p>
<p class="H3"><a name="Q4"></a>Q4 - 2022</p>
<p>Common label:</p>
"""
    markdown = """
Q1 - 2023
Common label:
Q4 - 2022
Common label:
"""

    promoted = promote_markdown_headings(markdown, html)

    assert promoted.index("### Q1 - 2023") < promoted.index("Common label:")
    assert promoted.index("### Q4 - 2022") > promoted.index("Common label:")
