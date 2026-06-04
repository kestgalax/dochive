# Agent Instructions

## Project Overview

Dochive is a Python CLI tool for mirroring HTML documentation into a Markdown-first repository. It produces Markdown page files with YAML frontmatter, `_index.yaml` files, global catalog YAML files, deterministic URL/file mappings, and optional media asset output.

Dochive supports MadCap WebHelp through explicit TOC discovery from `Data/HelpSystem.xml`. Wiki.js-style sites are supported through link-based discovery and cleanup heuristics for extensionless URLs, language prefixes, service routes, permalink heading anchors, and repeated site chrome.

## Repository Layout

- `src/dochive/` contains the CLI entrypoint and library modules.
- `tests/` contains focused pytest coverage for crawling, URL utilities, Markdown normalization, and writer layout behavior.
- `docs/` contains usage notes, roadmap material, and stage artifacts.
- User-facing docs are bilingual pairs: `README.md` / `README.ru.md`, `docs/USAGE.md` / `docs/USAGE.ru.md`, and `CHANGELOG.md` / `CHANGELOG.ru.md`. Keep paired English and Russian docs aligned when changing install, usage, license, dependency, changelog, or responsible-use text.
- `CHANGELOG.md` at the repository root is what GitHub shows as the Changelog tab next to README and License.
- Use `dochive changelog guide` for the bilingual notes format, then `dochive changelog apply --notes-file <path>` to prepend a release to both changelog files.
- `LICENSE` and `NOTICE` contain project licensing and attribution details.
- `main_page/`, `mirror/`, `.tmp-test-runs/`, `.crawl4ai-data/`, `.playwright-browsers/`, and `tmp*` directories are generated, mirrored, cached, or temporary data. Do not edit them unless the task explicitly targets those artifacts.

## Development Commands

Use Python 3.10 or newer.

```bash
python -m pip install -e .
python -m dochive --help
python -m pytest
```

Install optional Crawl4AI support only when needed:

```bash
python -m pip install -e ".[crawl4ai]"
```

`certifi` is an intentional required dependency for HTTPS certificate bundle handling in TOC and asset downloads. `crawl4ai` stays optional because local HTML mirroring should work without browser crawling dependencies.

In some local shells, `python` or `py` may not be available on `PATH`. Before assuming a command is broken, check whether the virtual environment is activated or whether another Python launcher is available.

## Working Rules

- Keep generated mirrors, caches, temp directories, `__pycache__/`, and `*.egg-info/` out of commits.
- Prefer small, deterministic changes that preserve stable URL-to-file mapping and stable Markdown/YAML output.
- When changing mirror, writer, parser, or normalizer behavior, add or update focused pytest tests near the existing tests.
- When changing MadCap TOC discovery or Wiki.js-style link discovery/cleanup behavior, add focused tests near `tests/test_url_utils.py`, `tests/test_markdown_normalizer.py`, or writer layout tests as appropriate.
- Keep documentation updates concise and aligned with `README.md`, `README.ru.md`, `docs/USAGE.md`, `docs/USAGE.ru.md`, `pyproject.toml`, `LICENSE`, and `NOTICE`.
