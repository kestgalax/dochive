# Stage 6. Incremental Sync

Status: completed

## Intent

Make repeated runs inspectable by comparing the new mirror output with the previous `_catalog/pages.yaml`.

## Changes

- Read previous page hashes before overwriting catalogs.
- Write `_catalog/sync.yaml`.
- Report added, changed, unchanged, and deleted page paths.
- Include sync counts in `_catalog/summary.yaml`.
- Include `sync.yaml` in `catalog` output.

## Files Touched

- `src/dochive/writer.py`
- `src/dochive/cli.py`
- `.gitignore`

## Verification

- `python -m compileall src`
- First run to a new output:
  - `added: 2`
  - `changed: 0`
  - `unchanged: 0`
  - `deleted: 0`
- Second identical run:
  - `added: 0`
  - `changed: 0`
  - `unchanged: 2`
  - `deleted: 0`
- Reduced-depth run:
  - `changed: 1`
  - `deleted: 1`

## Known Limitations

This stage compares generated Markdown content hashes only. It does not yet remove deleted files from disk or produce Git commits.
