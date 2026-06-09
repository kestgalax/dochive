from dochive.html_extract import (
    drop_madcap_toc_anchor_links,
    extract_html_toc_link_labels,
    inject_html_tables,
    promote_markdown_headings,
)
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


def test_injects_clean_html_table_for_multiline_wikijs_table() -> None:
    html = """
<figure class="table">
  <table>
    <tbody>
      <tr>
        <td style="color:red" rowspan="2">
          <p><strong>Цели</strong></p>
          <ul><li>Первый пункт</li><li>Второй пункт</li></ul>
        </td>
        <td><p><a href="/ru/next">Следующая страница</a></p></td>
      </tr>
      <tr><td><p><em>Выход</em></p></td></tr>
    </tbody>
  </table>
</figure>
"""
    markdown = """
# Фаза
| **Цели**
  * Первый пункт
  * Второй пункт

 | [Следующая страница](https://example.com/ru/next)
 |
| --- | --- |
| | *Выход* |
**Участники**
  * Участник

## После
"""

    assert inject_html_tables(markdown, html, "https://example.com/ru/current") == """# Фаза

<table header="row">
<tr>

<td rowspan="2">

**Цели**
- Первый пункт
- Второй пункт

</td>
<td>

[Следующая страница](https://example.com/ru/next)

</td>
</tr>

<tr>

<td>

*Выход*

</td>
</tr>

</table>


## После
"""


def test_inject_html_tables_keeps_paragraph_after_regular_markdown_table() -> None:
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    markdown = """
| A | B |
| --- | --- |
| C | D |
Paragraph after table.
"""

    assert inject_html_tables(markdown, html, "https://example.com/docs") == """{% table header="row" %}

---

*  {% colwidth=[256] %}
   A
*  {% colwidth=[256] %}
   B

{% /table %}
Paragraph after table.
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
[Введение Example Product](../_index.md) > План развития продукта
# План развития продукта
### Q4 - 2026
[Q4 - 2026](#Q3 - 2026) [Q3 - 2026](#Q2 - 2026) [Q2 - 2026](#Q1 - 2026)
[Q1 - 2026](#Q4 - 2025) [Q4 - 2025](#Q3_25)
[Q4 - 2023](#Q3 - 2023) [Q3 - 2023](#Q3_23)

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
            "Q4_23": "Q4 - 2023",
            "Q3_23_alt": "Q3 - 2023",
        },
    ) == (
        "[Введение Example Product](../_index.md) > План развития продукта\n"
        "# План развития продукта\n"
        "### Q4 - 2026\n\n"
        "  * Обновленные модули.\n"
    )


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


def test_drops_generic_footer_notice_block() -> None:
    markdown = """
# Article title

Main article text.

[Product page](https://docs.example.com/product)

Legal notice: this documentation is provided under the public offer terms.

Press Ctrl+Enter to report a documentation issue.
"""

    assert normalize_markdown(markdown) == "# Article title\n\nMain article text.\n"


def test_drops_generic_tail_powered_by_footer() -> None:
    markdown = """
# Article title

Main article text.

2026 Example Docs. Все права защищены. | Powered by [Wiki.js](https://wiki.js.org)
"""

    assert normalize_markdown(markdown) == "# Article title\n\nMain article text.\n"


def test_keeps_mid_article_engine_mentions() -> None:
    markdown = """
# Article title

This article explains how Powered by Wiki.js footers work.

Useful content after the mention.
"""

    assert normalize_markdown(markdown) == (
        "# Article title\n\n"
        "This article explains how Powered by Wiki.js footers work.\n\n"
        "Useful content after the mention.\n"
    )


def test_normalizes_inline_heading_permalinks() -> None:
    markdown = """
# [¶](#¶ Журнал изменений) Журнал изменений
## [#](#install) Install
### []( #empty ) Empty label
#### [¶](https://example.com/docs/page#absolute) **Absolute Link**
##### [¶](#¶ QA (with parentheses)) QA (with parentheses)
## ¶ AI
## [¶](#¶ AI) AI
"""

    assert normalize_markdown(markdown) == (
        "# Журнал изменений\n"
        "## Install\n"
        "### Empty label\n"
        "#### Absolute Link\n"
        "##### QA (with parentheses)\n"
        "## AI\n"
    )


def test_trims_leading_wikistyle_navigation_before_plain_title_and_subheading() -> None:
    markdown = """
Wiki Example. Knowledge base.
Search...
[](https://example.com/t)
[](https://example.com/login)
[Structure](https://example.com/ru/structure)
Regulations
[Standard](https://example.com/ru/standard)[Enterprise](https://example.com/ru/enterprise)
  * /
[advices](../_index.md)

Principles for working on tasks
## [¶](https://example.com/advices/work#principle-1) Principle 1
Body text.
"""

    assert normalize_markdown(markdown) == "Principles for working on tasks\n## Principle 1\nBody text.\n"


def test_drops_wiki_back_navigation_h6_headings() -> None:
    markdown = """Детализация требований (Enterprise)
###### назад
###### [__назад__](https://wiki.service.sdpro.naumen.ru/методика-внедрения/enterprise)

<table header="row">
<tr>
<td>Ответственный</td>
</tr>
</table>
"""

    assert normalize_markdown(markdown) == """Детализация требований (Enterprise)

<table header="row">
<tr>
<td>Ответственный</td>
</tr>
</table>
"""


def test_drops_wiki_back_navigation_h6_anywhere_in_document() -> None:
    markdown = """## Section
Body before back link.
###### [_**_назад_**_](https://wiki.example.com/parent)
Body after back link.
"""

    assert normalize_markdown(markdown) == """## Section
Body before back link.
Body after back link.
"""


def test_keeps_non_back_h6_and_non_h6_back_text() -> None:
    markdown = """###### Назад к списку
## назад
Перейдите по ссылке назад.
###### [back to overview](https://example.com/overview)
"""

    assert normalize_markdown(markdown) == """###### Назад к списку
## назад
Перейдите по ссылке назад.
###### [back to overview](https://example.com/overview)
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


def test_iframe_converted_to_link() -> None:
    from dochive.html_extract import parse_html_document

    html = '''
<h1>Документы</h1>
<p>Список документов:</p>
<iframe class="airtable-embed" src="https://airtable.com/embed/app7pUKjVrkuUDJdv/shrokR65WxEtk8tOq?backgroundColor=blue&viewControls=on" frameborder="0" onmousewheel="" width="100%" height="200" style="background: transparent; border: 1px solid #ccc;"></iframe>
<p>Конец раздела.</p>
'''
    result = parse_html_document(html, "https://example.com/")

    # Проверяем, что iframe преобразован в ссылку
    assert "https://airtable.com/embed/app7pUKjVrkuUDJdv/shrokR65WxEtk8tOq?backgroundColor=blue&viewControls=on" in result.markdown
    # Проверяем, что ссылка оформлена как markdown
    assert "[" in result.markdown and "]" in result.markdown
    # Проверяем, что iframe добавлен в assets
    assert len(result.assets) == 1
    assert result.assets[0].source == "https://airtable.com/embed/app7pUKjVrkuUDJdv/shrokR65WxEtk8tOq?backgroundColor=blue&viewControls=on"
    assert result.assets[0].kind == "files"


def test_normalize_markdown_drops_empty_links_before_named_link() -> None:
    markdown = (
        "Актуально для версии 3.0 и выше. Описание для прежних версий доступно "
        "[](https://www.naumen.ru/docs/sd/nsdpro/Content/CFG_act/audit_KE_add_old.htm)"
        "[по ссылке](https://www.naumen.ru/docs/sd/nsdpro/Content/route/route_card_old.htm).\n"
    )
    normalized = normalize_markdown(markdown, clean=False)
    assert "[](https://www.naumen.ru/docs/sd/nsdpro/Content/CFG_act/audit_KE_add_old.htm)" not in normalized
    assert (
        "[по ссылке](https://www.naumen.ru/docs/sd/nsdpro/Content/route/route_card_old.htm)"
        in normalized
    )


def test_normalize_markdown_preserves_image_links() -> None:
    markdown = "![alt](thumb.png)\n"
    normalized = normalize_markdown(markdown, clean=False)
    assert normalized == "![alt](thumb.png)\n"


def test_normalize_markdown_keeps_empty_links_inside_code_fences() -> None:
    markdown = "```\n[](https://example.com/page.htm)\n```\n"
    normalized = normalize_markdown(markdown, clean=False)
    assert "[](https://example.com/page.htm)" in normalized


def test_extract_html_toc_link_labels_reads_madcap_toc() -> None:
    html = """
    <ul class="TOC">
      <li><a href="#006">Копирование текста и таблиц</a></li>
      <li><a href="#005">Работа с таблицами</a></li>
    </ul>
    """
    assert extract_html_toc_link_labels(html) == (
        "Копирование текста и таблиц",
        "Работа с таблицами",
    )


def test_normalize_markdown_drops_madcap_intra_page_toc_block() -> None:
    markdown = "\n".join(
        [
            "### Редактор Froala",
            "",
            "- [Копирование текста и таблиц](https://example.com/input_field_RTF.htm)",
            "- [Работа с таблицами](https://example.com/input_field_RTF.htm)",
            "",
            "На панели инструментов редактора Froala размещаются:",
        ]
    )
    toc_labels = ("Копирование текста и таблиц", "Работа с таблицами")
    normalized = normalize_markdown(
        markdown,
        anchor_headings={"006": "Копирование текста и таблиц", "005": "Работа с таблицами"},
        toc_link_labels=toc_labels,
    )
    assert "Копирование текста и таблиц" not in normalized
    assert "Работа с таблицами" not in normalized
    assert "### Редактор Froala" in normalized
    assert "На панели инструментов редактора Froala размещаются:" in normalized


def test_promote_markdown_headings_does_not_insert_headings_for_madcap_toc() -> None:
    html = """
    <p class="H3">Редактор Froala</p>
    <ul class="TOC">
      <li><a href="#006">Копирование текста и таблиц</a></li>
      <li><a href="#005">Работа с таблицами</a></li>
    </ul>
    <p>На панели инструментов редактора Froala размещаются:</p>
    <p class="H4"><a name="006"></a>Копирование текста и таблиц</p>
    <p>При вставке скопированного текста и таблиц сохраняется исходное форматирование.</p>
    <p class="H4"><a name="005"></a>Работа с таблицами</p>
    <p>Чтобы изменить параметры ячейки таблицы, нажмите на ячейку.</p>
    """
    page_url = "https://example.com/input_field_RTF.htm"
    markdown = "\n".join(
        [
            "Редактор Froala",
            "",
            f"- [Копирование текста и таблиц]({page_url}#006)",
            f"- [Работа с таблицами]({page_url}#005)",
            "",
            "На панели инструментов редактора Froala размещаются:",
            "",
            "При вставке скопированного текста и таблиц сохраняется исходное форматирование.",
            "",
            "Чтобы изменить параметры ячейки таблицы, нажмите на ячейку.",
        ]
    )
    processed = promote_markdown_headings(drop_madcap_toc_anchor_links(markdown, html), html)
    lines = processed.splitlines()
    froala_index = lines.index("### Редактор Froala")
    copy_index = lines.index("#### Копирование текста и таблиц")
    assert copy_index > froala_index
    assert "На панели инструментов редактора Froala размещаются:" in lines[froala_index + 1 : copy_index]
    assert lines[froala_index + 1 : copy_index].count("####") == 0


def test_normalize_markdown_keeps_unrelated_same_page_links() -> None:
    markdown = "- [Скачать PDF](https://example.com/guide.htm)"
    normalized = normalize_markdown(
        markdown,
        anchor_headings={"pdf": "PDF"},
        toc_link_labels=("Копирование текста и таблиц",),
    )
    assert normalized.strip() == markdown.strip()
