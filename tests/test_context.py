import json
from pathlib import Path

from dochive.cli import main
from dochive.context import build_context_index, retrieve_context, write_context_index
from dochive.models import MirrorConfig, Page
from dochive.writer import write_mirror


def test_context_index_chunks_markdown_by_heading_chain(tmp_path: Path) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/deploy.htm",
                canonical_url="https://example.com/docs/deploy.htm",
                title="Deployment",
                markdown=(
                    "# Deployment\n\n"
                    "Intro with database overview.\n\n"
                    "## Medium profile\n\n"
                    "Backend service and PostgreSQL database.\n\n"
                    "### Limits\n\n"
                    "CPU and RAM limits.\n"
                ),
                depth=0,
            )
        ],
        MirrorConfig(source="https://example.com/docs/deploy.htm", out_dir=tmp_path),
    )

    units = build_context_index(root)

    page = next(unit for unit in units if unit.kind == "page")
    medium = next(unit for unit in units if unit.uri.endswith("#deployment-medium-profile"))
    limits = next(unit for unit in units if unit.uri.endswith("#deployment-medium-profile-limits"))

    assert page.path == "docs/deploy.md"
    assert page.source_url == "https://example.com/docs/deploy.htm"
    assert "source_url" not in page.text
    assert medium.headings == ("Deployment", "Medium profile")
    assert "PostgreSQL database" in medium.text
    assert limits.headings == ("Deployment", "Medium profile", "Limits")


def test_context_index_uses_stable_unique_uris_for_repeated_headings(tmp_path: Path) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/release.htm",
                canonical_url="https://example.com/docs/release.htm",
                title="Release",
                markdown="# Notes\n\nFirst.\n\n# Notes\n\nSecond.\n",
                depth=0,
            )
        ],
        MirrorConfig(source="https://example.com/docs/release.htm", out_dir=tmp_path),
    )

    section_uris = [unit.uri for unit in build_context_index(root) if unit.kind == "section"]

    assert section_uris == [
        "mirror://example.com/docs/release.md#notes",
        "mirror://example.com/docs/release.md#notes-2",
    ]


def test_write_context_index_creates_jsonl_with_sections(tmp_path: Path) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/search.htm",
                canonical_url="https://example.com/docs/search.htm",
                title="Search",
                markdown="# Search\n\nFind documents with запрос.\n",
                depth=0,
            )
        ],
        MirrorConfig(source="https://example.com/docs/search.htm", out_dir=tmp_path),
    )

    index_path = write_context_index(root)
    records = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]

    assert index_path == root / "_catalog" / "context_index.jsonl"
    assert [record["kind"] for record in records] == ["page", "section"]
    assert records[1]["headings"] == ["Search"]
    assert "запрос" in records[1]["terms"]


def test_retrieve_context_scores_headings_above_body_matches_and_traces(tmp_path: Path) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/a.htm",
                canonical_url="https://example.com/docs/a.htm",
                title="A",
                markdown="# Database Profile\n\nShort heading match.\n",
                depth=0,
            ),
            Page(
                source_url="https://example.com/docs/b.htm",
                canonical_url="https://example.com/docs/b.htm",
                title="B",
                markdown="# Other\n\nThis body mentions database profile once.\n",
                depth=0,
            ),
        ],
        MirrorConfig(source="https://example.com/docs/a.htm", out_dir=tmp_path),
    )
    write_context_index(root)

    results = retrieve_context(root, "database profile", limit=2)

    assert results[0].unit.uri.endswith("#database-profile")
    assert any(reason.startswith("matched heading") for reason in results[0].why)


def test_retrieve_context_supports_russian_terms(tmp_path: Path) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/ru.htm",
                canonical_url="https://example.com/docs/ru.htm",
                title="База знаний",
                markdown="# Настройка очереди\n\nОчередь сообщений и обработчики.\n",
                depth=0,
            )
        ],
        MirrorConfig(source="https://example.com/docs/ru.htm", out_dir=tmp_path),
    )
    write_context_index(root)

    results = retrieve_context(root, "очередь сообщений", limit=1)

    assert results[0].unit.headings == ("Настройка очереди",)
    assert "очередь" in results[0].unit.terms


def test_index_and_retrieve_cli_smoke(tmp_path: Path, capsys) -> None:
    root = write_mirror(
        [
            Page(
                source_url="https://example.com/docs/cli.htm",
                canonical_url="https://example.com/docs/cli.htm",
                title="CLI",
                markdown="# Quick Start\n\nRun the command.\n",
                depth=0,
            )
        ],
        MirrorConfig(source="https://example.com/docs/cli.htm", out_dir=tmp_path),
    )

    assert main(["index", "--root", str(root)]) == 0
    assert (root / "_catalog" / "context_index.jsonl").exists()

    assert main(["retrieve", "--root", str(root), "--text", "quick start", "--format", "json", "--trace"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])

    assert payload["query"] == "quick start"
    assert payload["results"][0]["why"]
