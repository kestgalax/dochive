# Stage 5. Errors And Diagnostics

Status: completed

## Intent

Large documentation mirrors need explicit diagnostics. A successful CLI exit can still produce unresolved internal links, failed assets, or crawl failures that should be visible in machine-readable files.

## Changes

- Add a shared run result carrying pages and issues.
- Add `_catalog/errors.yaml`.
- Add error/warning counts to `_catalog/summary.yaml`.
- Include `errors.yaml` in `catalog` output.
- Preserve `pages.yaml`, `links.yaml`, `assets.yaml`, and `summary.yaml`.
- Add a negative local fixture with a missing page and missing asset.

## Files Touched

- `src/dochive/models.py`
- `src/dochive/local_source.py`
- `src/dochive/web_source.py`
- `src/dochive/writer.py`
- `src/dochive/cli.py`
- `src/dochive/url_utils.py`
- `examples/broken-html/index.html`

## Verification

- `python -m compileall src`
- `dochive mirror --source examples\broken-html --out .\mirror-test --max-depth 3 --save-assets images`
- Verified `mirror-test\broken-html\_catalog\errors.yaml` includes:
  - `local_link_missing`
  - `asset_missing`
- Verified `summary.yaml` includes `warnings: 2`.
- example web smoke with `--max-depth 0 --max-pages 1 --scope subtree` writes unresolved internal links to `errors.yaml`.

## Known Limitations

Diagnostics are still coarse-grained. The next iteration should distinguish policy skips, HTTP errors, robots preflight, and failed postprocessing.
