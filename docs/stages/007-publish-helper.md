# Stage 7. Publish Helper

Status: completed

## Intent

Add a controlled Git helper around generated mirrors so users can inspect, initialize, commit, and optionally push mirror output without hand-writing Git commands every time.

## Changes

- Add `dochive publish`.
- Support `--dry-run`.
- Support optional `--init`.
- Support `--message`.
- Support optional `--push`.

## Files Touched

- `src/dochive/publish.py`
- `src/dochive/cli.py`

## Verification

- `python -m compileall src`
- `dochive publish --help`
- `dochive publish --root .\mirror-test\local-html --dry-run`
- `dochive publish --root .\mirror-test\local-html --dry-run --init --message "Update mirror"`
- Verified `--init --dry-run` prints planned Git actions without creating a repository.

## Known Limitations

The helper does not manage remotes yet. Users must configure the Git remote themselves before `--push`.
