from __future__ import annotations

from dochive.html_extract import extract_html_headings, promote_markdown_headings


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
