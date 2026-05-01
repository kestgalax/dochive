# Stage 2. Catalog Reporting

Status: completed

## Intent

Make each mirror run easier to inspect before deeper work on assets, errors, incremental sync, and bot/search integration.

## Changes

- Add a human-readable `_catalog/summary.yaml`.
- Include page, link, asset, and unresolved-link counts.
- Print summary path from the CLI.
- Keep the existing `pages.yaml`, `links.yaml`, and `assets.yaml` contracts.

## Files Touched

- `src/dochive/writer.py`
- `src/dochive/cli.py`

## Verification

- `python -m compileall src`
- `dochive mirror --source examples\local-html --out .\mirror-test --max-depth 3 --save-assets images,files`
- `dochive catalog --root .\mirror-test\local-html`
- Verified `mirror-test\local-html\_catalog\summary.yaml` contains:
  - `pages: 2`
  - `links_internal: 2`
  - `links_internal_unresolved: 0`
  - `assets_localized: 1`

## Known Limitations

This is not yet a full error report. Broken HTTP requests, failed assets, and deleted pages will move into a later `errors.yaml` and incremental sync stage.
