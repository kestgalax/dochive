from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SECTION_ORDER = ("added", "changed", "deprecated", "removed", "fixed", "security")
SECTION_TITLES = {
    "en": {
        "added": "Added",
        "changed": "Changed",
        "deprecated": "Deprecated",
        "removed": "Removed",
        "fixed": "Fixed",
        "security": "Security",
    },
    "ru": {
        "added": "Added",
        "changed": "Changed",
        "deprecated": "Deprecated",
        "removed": "Removed",
        "fixed": "Fixed",
        "security": "Security",
    },
}

LANG_MARKERS = {
    "en": ("[en]", "<!-- en -->", "---en---"),
    "ru": ("[ru]", "<!-- ru -->", "---ru---"),
}

HEADER_VERSION_RE = re.compile(r"^version:\s*(.+)\s*$", re.IGNORECASE)
HEADER_DATE_RE = re.compile(r"^date:\s*(.+)\s*$", re.IGNORECASE)
HEADER_BRANCH_RE = re.compile(r"^branch:\s*(.+)\s*$", re.IGNORECASE)
SECTION_HEADING_RE = re.compile(r"^#{2,3}\s+(added|changed|deprecated|removed|fixed|security)\s*$", re.IGNORECASE)
VERSION_HEADING_RE = re.compile(r"^##\s+\[(?P<version>[^\]]+)\]\s*[—-]\s*(?P<release_date>.+?)\s*$")

CHANGELOG_FILES = {
    "en": "CHANGELOG.md",
    "ru": "CHANGELOG.ru.md",
}


@dataclass
class ChangelogDraft:
    version: str
    release_date: str
    branch: str = ""
    sections: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def bullets(self, lang: str, section: str) -> list[str]:
        return self.sections.get(lang, {}).get(section, [])


def changelog_command(args: argparse.Namespace) -> int:
    if args.changelog_command == "guide":
        print(CHANGELOG_AGENT_GUIDE.strip())
        return 0

    repo_root = args.repo.resolve()
    notes = _read_notes(args)
    if not notes.strip():
        print("error: changelog notes are empty.", file=sys.stderr)
        return 2

    try:
        draft = parse_changelog_notes(notes)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.version:
        draft.version = args.version.strip()
    if args.date:
        draft.release_date = args.date.strip()
    if args.branch:
        draft.branch = args.branch.strip()
    if not draft.version:
        print("error: version is required (in notes or --version).", file=sys.stderr)
        return 2
    if not draft.release_date:
        draft.release_date = date.today().isoformat()

    rendered = {lang: render_release_section(draft, lang) for lang in ("en", "ru")}
    if args.changelog_command == "draft":
        print(rendered["en"], end="" if rendered["en"].endswith("\n") else "\n")
        print("---")
        print(rendered["ru"], end="" if rendered["ru"].endswith("\n") else "\n")
        return 0

    if args.dry_run:
        for lang, path in CHANGELOG_FILES.items():
            print(f"# {path}")
            print(rendered[lang], end="" if rendered[lang].endswith("\n") else "\n")
        return 0

    try:
        apply_changelog_draft(repo_root, draft)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Updated {CHANGELOG_FILES['en']} and {CHANGELOG_FILES['ru']} with [{draft.version}]")
    return 0


def parse_changelog_notes(text: str) -> ChangelogDraft:
    draft = ChangelogDraft(version="", release_date="")
    current_lang: str | None = None
    current_section: str | None = None
    header_done = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if not header_done:
            if match := HEADER_VERSION_RE.match(line):
                draft.version = match.group(1).strip()
                continue
            if match := HEADER_DATE_RE.match(line):
                draft.release_date = match.group(1).strip()
                continue
            if match := HEADER_BRANCH_RE.match(line):
                draft.branch = match.group(1).strip()
                continue
            if _is_lang_marker(line):
                header_done = True
                current_lang = _lang_from_marker(line)
                current_section = None
                continue
            if SECTION_HEADING_RE.match(line):
                header_done = True
                current_lang = current_lang or "en"
                current_section = SECTION_HEADING_RE.match(line).group(1).lower()
                continue
            if line.startswith(("- ", "* ")):
                header_done = True
                current_lang = current_lang or "en"
                current_section = current_section or "added"
                draft.sections.setdefault(current_lang, {}).setdefault(current_section, []).append(line[2:].strip())
                continue
            continue

        if lang := _lang_from_marker(line):
            current_lang = lang
            current_section = None
            continue

        if match := SECTION_HEADING_RE.match(line):
            if current_lang is None:
                current_lang = "en"
            current_section = match.group(1).lower()
            continue

        if line.startswith(("- ", "* ")):
            if current_lang is None:
                current_lang = "en"
            if current_section is None:
                current_section = "added"
            draft.sections.setdefault(current_lang, {}).setdefault(current_section, []).append(line[2:].strip())
            continue

        if current_section and current_lang:
            draft.sections.setdefault(current_lang, {}).setdefault(current_section, []).append(line)

    if not draft.sections:
        raise ValueError("no changelog bullets found; use [en]/[ru] blocks and ### Added/Fixed sections")
    return draft


def render_release_section(draft: ChangelogDraft, lang: str) -> str:
    lines = [f"## [{draft.version}] — {draft.release_date}", ""]
    if draft.branch:
        if lang == "ru":
            lines.append(f"Ветка `{draft.branch}`.")
        else:
            lines.append(f"Branch `{draft.branch}`.")
        lines.append("")

    for section in SECTION_ORDER:
        bullets = draft.bullets(lang, section)
        if not bullets:
            continue
        lines.append(f"### {SECTION_TITLES[lang][section]}")
        lines.append("")
        lines.extend(f"- {bullet}" for bullet in bullets)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def apply_changelog_draft(repo_root: Path, draft: ChangelogDraft) -> None:
    for lang, filename in CHANGELOG_FILES.items():
        path = repo_root / filename
        if not path.exists():
            raise ValueError(f"missing changelog file: {path}")
        content = path.read_text(encoding="utf-8")
        if f"## [{draft.version}]" in content:
            raise ValueError(f"version [{draft.version}] already exists in {filename}")
        updated = _insert_release_section(content, render_release_section(draft, lang))
        path.write_text(updated, encoding="utf-8")


def _insert_release_section(content: str, section: str) -> str:
    lines = content.splitlines()
    insert_at = _release_insertion_index(lines)
    block = section.splitlines()
    if insert_at < len(lines) and lines[insert_at].strip():
        block.append("")
    new_lines = lines[:insert_at] + block + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def _release_insertion_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if VERSION_HEADING_RE.match(line.strip()):
            return index
    return len(lines)


def _read_notes(args: argparse.Namespace) -> str:
    if args.notes_file:
        if str(args.notes_file) == "-":
            return sys.stdin.read()
        return Path(args.notes_file).read_text(encoding="utf-8")
    if args.notes:
        return args.notes
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _is_lang_marker(line: str) -> bool:
    return _lang_from_marker(line) is not None


def _lang_from_marker(line: str) -> str | None:
    normalized = line.strip().casefold()
    for lang, markers in LANG_MARKERS.items():
        if normalized in {marker.casefold() for marker in markers}:
            return lang
    return None


CHANGELOG_AGENT_GUIDE = """
# Dochive changelog notes format

Use this format when packaging chat/session context into CHANGELOG entries.
Save notes to a file and run:

  dochive changelog apply --notes-file notes.md
  cat notes.md | dochive changelog apply

Commands:
  dochive changelog guide   # print this guide
  dochive changelog draft   # preview English and Russian sections
  dochive changelog apply   # prepend a release to CHANGELOG.md and CHANGELOG.ru.md

Notes template:

version: 0.2.1
date: 2026-06-04
branch: codex/feature-branch

[en]
### Added
- User-visible change in English.

### Fixed
- Bug fix in English.

[ru]
### Added
- То же изменение по-русски.

### Fixed
- Исправление по-русски.

Rules:
- Keep section names in English (`### Added`, `### Fixed`, ...).
- Put bullets under [en] and [ru]; do not mix languages in one block.
- Use `version`, `date`, and optional `branch` in the header.
- One release per notes file; `apply` refuses duplicate versions.
"""


def add_changelog_parser(subparsers: argparse._SubParsersAction) -> None:
    changelog = subparsers.add_parser(
        "changelog",
        help="Package session notes into Keep a Changelog release sections.",
    )
    changelog_sub = changelog.add_subparsers(dest="changelog_command", required=True)

    for name, help_text in (
        ("guide", "Print the notes format for agents and chat sessions."),
        ("draft", "Render release sections without modifying files."),
        ("apply", "Prepend a release to CHANGELOG.md and CHANGELOG.ru.md."),
    ):
        parser = changelog_sub.add_parser(name, help=help_text)
        _add_changelog_arguments(parser)
        if name == "apply":
            parser.add_argument("--dry-run", action="store_true", help="Show file updates without writing.")


def _add_changelog_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root with CHANGELOG files.")
    parser.add_argument("--notes-file", help="Notes file path. Use - for stdin.")
    parser.add_argument("--notes", help="Inline notes text.")
    parser.add_argument("--version", help="Override version from notes.")
    parser.add_argument("--date", help="Override release date from notes (YYYY-MM-DD).")
    parser.add_argument("--branch", help="Override branch/context line from notes.")
