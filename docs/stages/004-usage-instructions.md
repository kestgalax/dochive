# Stage 4. Usage Instructions

Status: completed

## Intent

Provide a practical instruction file that explains how to run the CLI in this Windows/Codex environment and how to use the first implemented workflows.

## Changes

- Added `docs/USAGE.md`.
- Linked project docs from `README.md`.
- Documented:
  - PowerShell `PATH` setup.
  - Local HTML mirroring.
  - Web subtree mirroring.
  - Selector-based extraction tuning.
  - Catalog inspection.
  - File-based query.

## Files Touched

- `docs/USAGE.md`
- `README.md`
- `docs/ROADMAP.md`

## Verification

- Reviewed commands against current CLI flags.
- Confirmed `dochive --help`, `mirror --help`, `catalog`, and `query` commands exist.

## Known Limitations

The instructions assume the bundled Python runtime path used by this Codex desktop workspace. A standalone install guide for a fresh machine should be added later.
