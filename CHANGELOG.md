# Changelog

[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Agent skills `dochive-mirror` and `dochive-mirror-verify` under `skills/` for structure-first mirroring, volume-based run planning, and post-mirror verification. **Experimental:** workflows are not fully tested across sites and agent runtimes yet.
- `setup.sh` and `setup.bat` installers (pochemuchka-style) for OpenCode, Claude Code, Codex, and Cursor.
- `skills/dochive-mirror-verify/scripts/check_mirror.sh` for automated placeholder, error, and live-site link-leak checks.

### Changed

- Agent skills: preflight step, greenfield/incremental/refresh/verify-only modes, `--out` vs `mirror_root` guidance, and warnings against `--structure-mode links` on existing MadCap mirrors; reinstall with `./setup.sh --target cursor --force` after `git pull`.
- Stop tracking local IDE skill installs (`.cursor/skills/`, `.opencode/skills/`); canonical source stays in `skills/`.
- Short agent skills guide: `docs/SKILLS.md` / `docs/SKILLS.ru.md`.

## [0.2.5] — 2026-06-08

### Added

- `dochive relink` rewrites absolute Markdown links to internal mirror paths offline using `_catalog/structure.yaml` and `pages.yaml`, with `--dry-run` and `--path-prefix` for scoped runs.
- Tests in `tests/test_relink.py` and `tests/test_markdown_normalizer.py` for relink and empty-link cleanup.

### Changed

- `docs/USAGE.md` / `docs/USAGE.ru.md`: document incremental `relink` workflow after partial mirroring.

### Fixed

- Markdown normalization drops empty link labels `[](url)` produced from invalid nested MadCap anchors (for example `доступно [](...)[по ссылке](...)` becomes `доступно [по ссылке](...)`), without touching `![](...)` or fenced code.

## [0.2.4] — 2026-06-08

Branch `fix/incremental-cross-section-links`: incremental partial mirror link rewrite and catalog preservation.

### Fixed

- Partial mirror runs rewrite internal links to pages already recorded in `_catalog/pages.yaml`, not only URLs crawled in the current run (for example introduction links to QuickStart after mirroring sections separately).
- Partial mirror no longer replaces previously mirrored sections with placeholder markdown when a different TOC branch is mirrored into the same output directory.
- Regression where catalog path merge expanded `sync_roots` to the entire mirror and dropped out-of-scope entries from `_catalog/pages.yaml`.

### Changed

- `dochive mirror` prints incremental progress on stderr (`Reading catalog...`, `Writing N pages...`, `Updating catalog...`, and related steps).
- Partial sync refreshes folder `_index.yaml` files only within the current sync scope instead of the full mirror tree.
- Crawl4AI shutdown closes the browser explicitly with a timeout; localized image assets are skipped when the target file already exists on disk.
- Asset downloads use a 30-second URL timeout.

### Added

- Tests in `tests/test_writer_links.py` for cross-section link rewrite and partial-mirror catalog and disk preservation.

## [0.2.3] — 2026-06-08

Branch `fix/madcap-spoiler-podrobnee`: restore MadCap «Подробнее» spoiler blocks in Gramax output.

### Fixed

- MadCap `MCDropDown` «Подробнее» links (`[Подробнее](#)` rewritten to the current page) are recognized again and rendered as Gramax `<details>` / `<summary>` blocks instead of a self-link on the same page (for example change-list entries on Naumen NSD Pro `stable-26`).

## [0.2.2] — 2026-06-08

Branch `fix/gramax-inline-paragraph-images`: Gramax-safe spacing for inline icons in paragraph text.

### Changed

- `docs/USAGE.md` / `docs/USAGE.ru.md`: document block spacing for small icons in paragraph text; list-item icons still use the inline list layout.

### Fixed

- Small MadCap icons embedded mid-sentence in paragraph text are split onto their own `<image>` line with blank lines before and after, so Gramax renders them correctly (for example tile icons on Naumen NSD Pro quick-start pages). List-item icons keep the existing inline list layout.

## [0.2.1] — 2026-06-04

Branch `fix/madcap-tables-comments-colwidth`: MadCap table recovery, Gramax notes, and page titles from HTML.

### Added

- Convert source HTML tables into Gramax `{% table %}` blocks with per-cell `{% colwidth=[…] %}` (256 px default, 512 px for wide columns); keep `rowspan`/`colspan` tables as HTML fallback.
- Replace lossy Crawl4AI pipe tables with cleaned HTML tables; absorb orphan list bullets that belonged inside table cells.
- Map MadCap `<p class="comment">` paragraphs to Gramax `:::note:false` callouts during web mirror.
- Insert MadCap `<h2>` section titles immediately before each recovered Gramax table block.
- Use the HTML `<title>` or `<h1>` text for mirrored page metadata when Crawl4AI or navigation labels are shorter than the document title.

### Fixed

- Duplicate `##` section headings between consecutive Gramax tables when heading promotion and table injection overlapped.
- Leftover pipe rows, loose `|`, and orphan bullets after `{% /table %}` on MadCap metric pages.
- Stray `-` lines inside table cells when list items used nested `<p>` markup (`<ul class="tab">` in cells).
- Gramax page header showing a short TOC label while the article body kept the full MadCap document title.

## [0.2.0] — 2026-06-04

Branch `codex/madcap-heading-recovery`: MadCap WebHelp heading recovery and Gramax-safe list icons.

### Added

- Restore missing MadCap headings (`p class="H1"`–`H6"`) by matching the next paragraph or first list item when Crawl4AI drops the heading line from Markdown.
- Insert recovered headings before an `<image>` / `<video>` block when a diagram sits immediately before the follower text from HTML (fixes “image above heading”, e.g. `### Границы Процесса` on Naumen NSD Pro pages).
- Inline list icon mode: images with the longest side ≤ `--image-inline-max-px` (default 48) use a Gramax-friendly layout (icon on its own list line, text on the next line; no `scale` attribute).
- CLI flag `--image-inline-max-px` (`0` disables the behavior).
- Tests: `tests/test_html_extract.py`, `tests/test_writer_images.py`.

### Changed

- Documentation: `README.md` / `README.ru.md`, `docs/USAGE.md` / `docs/USAGE.ru.md`, `docs/stages/010-html-heading-recovery.md` — follower-text insertion and inline icons.

### Fixed

- Missing section titles such as «Общее описание» and «Основные положения Процесса» on MadCap pages after web mirror.
- Overscaled small list icons in Gramax caused by block-level `<image float="center">` on the same line as list text.
