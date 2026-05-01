from dochive.markdown_normalizer import normalize_markdown


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
