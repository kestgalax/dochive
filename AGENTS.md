# Agent Instructions

## Project Overview

Dochive is a Python CLI tool for mirroring HTML documentation into a Markdown-first repository. It produces Markdown page files with YAML frontmatter, `_index.yaml` files, global catalog YAML files, deterministic URL/file mappings, and optional media asset output.

## Repository Layout

- `src/dochive/` contains the CLI entrypoint and library modules.
- `tests/` contains focused pytest coverage for crawling, URL utilities, Markdown normalization, and writer layout behavior.
- `docs/` contains usage notes, roadmap material, and stage artifacts.
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

In some local shells, `python` or `py` may not be available on `PATH`. Before assuming a command is broken, check whether the virtual environment is activated or whether another Python launcher is available.

## Working Rules

- Keep generated mirrors, caches, temp directories, `__pycache__/`, and `*.egg-info/` out of commits.
- Prefer small, deterministic changes that preserve stable URL-to-file mapping and stable Markdown/YAML output.
- When changing mirror, writer, parser, or normalizer behavior, add or update focused pytest tests near the existing tests.
- Keep documentation updates concise and aligned with `README.md`, `docs/USAGE.md`, and `pyproject.toml`.
