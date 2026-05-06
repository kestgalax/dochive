# Stage 1. Markdown Quality And Noise Filtering

Status: completed

## Intent

Improve the quality of generated Markdown before expanding the crawler further. The first target is practical documentation sites that contain repeated menu/account/search chrome around the actual article.

## Changes

- Add a Markdown normalizer.
- Filter common UI/noise lines.
- Add CLI controls for Crawl4AI extraction:
  - `--content-selector`
  - `--exclude-selector`
  - `--exclude-tag`
  - `--noise-line`
  - `--no-clean-markdown`
- Keep cleanup conservative by default.

## Files Touched

- `src/dochive/markdown_normalizer.py`
- `src/dochive/models.py`
- `src/dochive/cli.py`
- `src/dochive/web_source.py`
- `src/dochive/local_source.py`

## Verification

- `python -m compileall src`
- `dochive mirror --source examples\local-html --out .\mirror-test --max-depth 3 --save-assets images,files`
- example documentation smoke test with `--max-depth 0 --max-pages 1 --scope subtree`
- Verified generated example documentation Markdown has:
  - `Account count: 0`
  - `Logout count: 0`
  - readable Russian title in UTF-8

## Known Limitations

Selector quality depends on the source documentation HTML. A site-specific selector may still be needed for best results.

Robots.txt handling is intentionally not enabled inside Crawl4AI yet because it returned zero pages without actionable diagnostics in the example documentation smoke test. This should be implemented with explicit preflight and `errors.yaml` reporting.
