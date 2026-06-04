# Changelog

[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
