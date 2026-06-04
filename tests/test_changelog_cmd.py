from __future__ import annotations

from pathlib import Path

import pytest

from dochive.changelog_cmd import apply_changelog_draft, parse_changelog_notes, render_release_section


NOTES = """
version: 0.2.1
date: 2026-06-10
branch: codex/example

[en]
### Added
- English feature.

### Fixed
- English fix.

[ru]
### Added
- Русская фича.

### Fixed
- Русское исправление.
"""


def test_parse_changelog_notes_reads_bilingual_sections() -> None:
    draft = parse_changelog_notes(NOTES)
    assert draft.version == "0.2.1"
    assert draft.release_date == "2026-06-10"
    assert draft.branch == "codex/example"
    assert draft.bullets("en", "added") == ["English feature."]
    assert draft.bullets("ru", "fixed") == ["Русское исправление."]


def test_render_release_section_includes_branch_line() -> None:
    draft = parse_changelog_notes(NOTES)
    english = render_release_section(draft, "en")
    assert english.startswith("## [0.2.1] — 2026-06-10")
    assert "Branch `codex/example`." in english
    assert "### Added" in english


def test_apply_changelog_draft_prepends_new_release(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md)\n\n## [0.2.0] — 2026-06-04\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.ru.md").write_text(
        "# История изменений\n\n[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md)\n\n## [0.2.0] — 2026-06-04\n",
        encoding="utf-8",
    )
    draft = parse_changelog_notes(NOTES)
    apply_changelog_draft(tmp_path, draft)

    english = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    russian = (tmp_path / "CHANGELOG.ru.md").read_text(encoding="utf-8")
    assert english.index("## [0.2.1]") < english.index("## [0.2.0]")
    assert russian.index("## [0.2.1]") < russian.index("## [0.2.0]")
    assert "English feature." in english
    assert "Русская фича." in russian


def test_apply_changelog_draft_rejects_duplicate_version(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text("## [0.2.1] — 2026-06-10\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.ru.md").write_text("## [0.2.1] — 2026-06-10\n", encoding="utf-8")
    draft = parse_changelog_notes(NOTES)
    with pytest.raises(ValueError, match="already exists"):
        apply_changelog_draft(tmp_path, draft)
