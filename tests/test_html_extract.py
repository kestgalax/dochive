from __future__ import annotations

from dochive.html_extract import (
    extract_html_headings,
    extract_html_tables,
    inject_html_comments,
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


def test_sanitize_table_keeps_ul_li_inside_td() -> None:
    tables = extract_html_tables(
        MADCAP_TABLE_WITH_TAB_LIST,
        "https://example.com/page.htm",
    )
    assert len(tables) == 1
    table = tables[0]
    assert "<ul>" in table
    assert "<li>" in table
    assert "M-INC1 Средний балл" in table
    assert "-  M-INC1" not in table


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
    assert "- M-INC1" not in injected
    assert "- M-INC2" not in injected
    assert "<table header=\"row\">" in injected
    assert "<ul>" in injected
    assert "M-INC1 Средний балл" in injected


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
    assert injected.count("<table header=\"row\">") == 2
    assert "between" in injected


def test_inject_html_comments_replaces_madcap_comment_paragraph() -> None:
    html = '<p class="comment">Если в карточке только одна вкладка, то ее название не отображается.</p>'
    markdown = "Если в карточке только одна вкладка, то ее название не отображается."
    injected = inject_html_comments(markdown, html)
    assert ":::note:true" in injected
    assert "ее название не отображается" in injected
    assert injected.strip().endswith(":::")


def test_sanitize_table_adds_colwidth_for_wide_description_column() -> None:
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
    assert "{% colwidth=[" in table
    match = table.split("{% colwidth=[", 1)[1].split("] %}", 1)[0]
    widths = [int(item) for item in match.split(",")]
    assert len(widths) == 3
    assert widths[2] > widths[0]


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
