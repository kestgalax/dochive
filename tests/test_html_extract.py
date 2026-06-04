from __future__ import annotations

from dochive.html_extract import (
    _cleanup_madcap_table_duplicates,
    _dedupe_adjacent_markdown_headings,
    _strip_orphan_headings_between_gramax_tables,
    extract_html_document_title,
    extract_html_headings,
    extract_html_tables,
    inject_html_comments,
    inject_html_table_section_headings,
    inject_html_tables,
    promote_markdown_headings,
)


MADCAP_H3_HTML = """
<html><body>
<h1>Title</h1>
<p class="H3" data-mc-autonum=""><span class="autonumber"><span></span></span>Общее описание</p>
<p>Follower paragraph unique start for section one.</p>
<p class="H3" data-mc-autonum=""><span class="autonumber"><span></span></span>Основные положения</p>
<ul class="FirstLevel">
<li value="1">List follower unique start for section two.</li>
</ul>
</body></html>
"""

MADCAP_MARKDOWN_WITHOUT_HEADINGS = """# Title
Follower paragraph unique start for section one.
  * List follower unique start for section two.
"""


def test_extract_html_headings_collects_following_snippets() -> None:
    headings = extract_html_headings(MADCAP_H3_HTML)
    assert len(headings) == 3
    assert headings[1].text == "Общее описание"
    assert headings[1].following_snippet.startswith("Follower paragraph unique")
    assert headings[2].text == "Основные положения"
    assert headings[2].following_snippet.startswith("List follower unique")


def test_promote_markdown_headings_inserts_missing_madcap_h3_headings() -> None:
    promoted = promote_markdown_headings(MADCAP_MARKDOWN_WITHOUT_HEADINGS, MADCAP_H3_HTML)
    lines = promoted.splitlines()
    assert lines[1] == "### Общее описание"
    assert lines[2] == "Follower paragraph unique start for section one."
    assert lines[3] == "### Основные положения"
    assert lines[4].startswith("  * List follower unique")


def test_promote_markdown_headings_matches_follower_with_markdown_link() -> None:
    html = """
    <html><body>
    <p class="H3">Objects</p>
    <ul><li><a href="req.htm">Service request</a> (SR) – short definition text.</li></ul>
    </body></html>
    """
    markdown = "  * [Service request](req.htm) (SR) – short definition text."
    promoted = promote_markdown_headings(markdown, html)
    assert promoted.splitlines()[0] == "### Objects"


def test_promote_markdown_headings_inserts_before_preceding_diagram() -> None:
    html = """
    <html><body>
    <p class="H3">Границы Процесса</p>
    <p class="ris"><img src="../Resources/Images/00/srm_01.png" /></p>
    <p>В рамках Процесса обрабатываются следующие типы ЗНО:</p>
    </body></html>
    """
    markdown = "\n".join(
        [
            "### Правила обработки",
            "Rules section content.",
            "",
            '<image src="./srm_01.png" width="1068px" height="459px"/>',
            "",
            "В рамках Процесса обрабатываются следующие типы ЗНО:",
            "  * ЗНО;",
        ]
    )
    promoted = promote_markdown_headings(markdown, html)
    lines = promoted.splitlines()
    heading_index = lines.index("### Границы Процесса")
    image_index = next(index for index, line in enumerate(lines) if "srm_01" in line)
    follower_index = next(index for index, line in enumerate(lines) if line.startswith("В рамках Процесса"))
    assert heading_index < image_index < follower_index


MADCAP_TABLE_WITH_TAB_LIST = """
<table class="TableStyle-PatternedRows">
<thead><tr>
<th>ID</th><th>Наименование показателя</th><th>Метрика</th>
</tr></thead>
<tbody>
<tr>
<td>G-INC1</td>
<td>Обеспечение высокого качества поддержки Услуг</td>
<td><ul class="tab"><li value="1">M-INC1 Средний балл</li></ul></td>
</tr>
</tbody>
</table>
"""


def test_cleanup_madcap_table_duplicates_removes_post_table_debris() -> None:
    markdown = "\n".join(
        [
            '{% table header="row" %}',
            "",
            "---",
            "",
            "*  {% colwidth=[256] %}",
            "   G-SLM1",
            "",
            "{% /table %}",
            "",
            "## Цели",
            "- M-SLM1 metric one",
            "| G-SLM2 | longer name column |",
            " |",
            "| G-SLM3 | another row |",
            "",
            "## Проблемные области",
            "Keep this paragraph.",
        ]
    )
    cleaned = _cleanup_madcap_table_duplicates(markdown)
    assert "## Цели" not in cleaned
    assert "Keep this paragraph" in cleaned
    assert "G-SLM2" not in cleaned
    assert "- M-SLM1 metric one" not in cleaned


def test_sanitize_table_renders_gramax_format_with_list_in_cell() -> None:
    tables = extract_html_tables(
        MADCAP_TABLE_WITH_TAB_LIST,
        "https://example.com/page.htm",
    )
    assert len(tables) == 1
    table = tables[0]
    assert table.startswith('{% table header="row" %}')
    assert "{% /table %}" in table
    assert "M-INC1 Средний балл" in table
    assert "*  {% colwidth=" in table
    assert "- M-INC1" in table
    assert "\n-\n" not in table


def test_inject_html_tables_absorbs_orphan_metric_bullets() -> None:
    markdown = "\n".join(
        [
            "## Цели и метрики",
            "- M-INC1 Средний балл",
            "- M-INC2 Процент инцидентов",
            "| ID | Наименование показателя | Метрика |",
            "| --- | --- | --- |",
            "| G-INC1 | Обеспечение высокого качества поддержки Услуг |",
            "| G-INC2 | Обеспечение высокой доступности |",
        ]
    )
    injected = inject_html_tables(markdown, MADCAP_TABLE_WITH_TAB_LIST, "https://example.com/page.htm")
    lines = injected.splitlines()
    table_line = next(index for index, line in enumerate(lines) if line.startswith('{% table header="row" %}'))
    before_table = "\n".join(lines[:table_line])
    assert "- M-INC1" not in before_table
    assert "- M-INC2" not in before_table
    assert '{% table header="row" %}' in injected
    assert "M-INC1 Средний балл" in injected
    assert "{% /table %}" in injected


def test_inject_html_tables_handles_two_tables_in_order() -> None:
    html = (
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>x</td></tr></table>"
        "<table><tr><th>C</th><th>D</th></tr><tr><td>2</td><td>y</td></tr></table>"
    )
    markdown = "\n".join(
        [
            "| A | B |",
            "| --- | --- |",
            "| 1 | x |",
            "between",
            "| C | D |",
            "| --- | --- |",
            "| 2 | y |",
        ]
    )
    injected = inject_html_tables(markdown, html, "https://example.com/page.htm")
    assert injected.count('{% table header="row" %}') == 2
    assert "between" in injected


def test_inject_html_comments_replaces_madcap_comment_paragraph() -> None:
    html = '<p class="comment">Если в карточке только одна вкладка, то ее название не отображается.</p>'
    markdown = "Если в карточке только одна вкладка, то ее название не отображается."
    injected = inject_html_comments(markdown, html)
    assert ":::note:true" in injected
    assert "ее название не отображается" in injected
    assert injected.strip().endswith(":::")


def test_sanitize_table_uses_column_width_for_header_and_body() -> None:
    html = """
    <table>
    <tr><th>№</th><th>Описание</th></tr>
    <tr><td>1</td><td>""" + "x" * 100 + """</td></tr>
    </table>
    """
    table = extract_html_tables(html, "https://example.com/gateway.htm")[0]
    wide_lines = [line for line in table.splitlines() if "{% colwidth=[512] %}" in line]
    assert len(wide_lines) == 2
    narrow_lines = [line for line in table.splitlines() if "{% colwidth=[256] %}" in line]
    assert len(narrow_lines) == 2


def test_sanitize_table_adds_colwidth_512_for_wide_cell() -> None:
    html = """
    <table>
    <tr><th>Параметр</th><th>Тип</th><th>Описание</th></tr>
    <tr>
    <td>host</td>
    <td>string</td>
    <td>Адрес шлюза и дополнительные пояснения по настройке подключения к внешним системам</td>
    </tr>
    </table>
    """
    tables = extract_html_tables(html, "https://example.com/gateway.htm")
    assert len(tables) == 1
    table = tables[0]
    assert "{% colwidth=[512] %}" in table
    assert "{% colwidth=[256] %}" in table


def test_promote_markdown_headings_keeps_existing_anchor_insertion() -> None:
    html = """
    <html><body>
    <h2 id="section-anchor">Section</h2>
    <p>Body after anchor.</p>
    </body></html>
    """
    markdown = "Body after anchor."
    promoted = promote_markdown_headings(markdown, html)
    assert promoted.splitlines()[0] == "## Section"


def test_extract_html_document_title_prefers_title_tag() -> None:
    html = (
        "<html><head><title>Метрики процесса \"Управление услугами\"</title></head>"
        "<body><h1>Fallback</h1></body></html>"
    )
    assert extract_html_document_title(html) == 'Метрики процесса "Управление услугами"'


def test_strip_orphan_headings_between_gramax_tables_removes_gap_duplicates() -> None:
    markdown = "\n".join(
        [
            '{% table header="row" %}',
            "",
            "---",
            "",
            "*  {% colwidth=[256] %}",
            "   A",
            "",
            "{% /table %}",
            "",
            "## Цели",
            "## Проблемные области",
            "",
            '{% table header="row" %}',
            "",
            "---",
            "",
            "*  {% colwidth=[256] %}",
            "   B",
            "",
            "{% /table %}",
        ]
    )
    stripped = _strip_orphan_headings_between_gramax_tables(markdown)
    assert "## Цели" not in stripped
    assert stripped.count("## Проблемные области") == 1


def test_dedupe_adjacent_markdown_headings() -> None:
    markdown = "## Проблемные области\n\n## Проблемные области\n\nBody\n"
    assert _dedupe_adjacent_markdown_headings(markdown).count("## Проблемные области") == 1


def test_inject_html_table_section_headings_inserts_h2_before_gramax_tables() -> None:
    html = """
    <h2>Цели</h2>
    <table><tr><td>A</td></tr></table>
    <table><tr><td>B</td></tr></table>
    <h2>Проблемные области</h2>
    <table><tr><td>C</td></tr></table>
    """
    markdown = '{% table header="row" %}\n\n---\n\n*  {% colwidth=[256] %}\n   A\n\n{% /table %}\n{% table header="row" %}\n\n---\n\n*  {% colwidth=[256] %}\n   B\n\n{% /table %}\n{% table header="row" %}\n\n---\n\n*  {% colwidth=[256] %}\n   C\n\n{% /table %}\n'
    injected = inject_html_table_section_headings(markdown, html)
    lines = injected.splitlines()
    assert lines[0] == "## Цели"
    assert lines[2].startswith("{% table")
    assert "## Проблемные области" in injected
    assert injected.count("## Цели") == 1


def test_cleanup_madcap_table_duplicates_drops_orphan_heading_and_debris() -> None:
    markdown = """{% table header="row" %}

---

*  {% colwidth=[256] %}
   G-SLM1

{% /table %}

## Цели
  * M-SLM1 metric one
| G-SLM2 | goal two |
 |
| G-SLM3 | goal three |

## Проблемные области

{% table header="row" %}

---

*  {% colwidth=[256] %}
   Е-SLM1

{% /table %}

## Метрики
| M-SLM2 | wide duplicate row |
| M-SLM3 | another duplicate |

Основные вопросы анкеты:
"""
    cleaned = _cleanup_madcap_table_duplicates(markdown)
    assert "## Цели" not in cleaned
    assert "M-SLM1 metric one" not in cleaned
    assert "G-SLM2" not in cleaned
    assert "## Проблемные области" in cleaned
    assert "## Метрики" not in cleaned
    assert "M-SLM2 | wide" not in cleaned
    assert "Основные вопросы анкеты:" in cleaned
