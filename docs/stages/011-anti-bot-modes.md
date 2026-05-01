# Stage 11. Anti-Bot Crawl Modes

## What Changed

- Added an `--anti-bot` CLI option with `off`, `basic`, `stealth`, and `aggressive` profiles.
- Made `basic` the default for web crawling.
- Applied the current `basic` profile through Crawl4AI settings:
  - random user agent mode;
  - simulated user interaction;
  - navigator override;
  - Crawl4AI magic mode.
- Kept `off` as the plain Crawl4AI behavior for diagnostics.
- Reserved `stealth` and `aggressive` as explicit future modes that currently fail with a clear message.

## Files Touched

- `src/dochive/cli.py`
- `src/dochive/models.py`
- `src/dochive/web_source.py`
- `docs/USAGE.md`
- `docs/ROADMAP.md`
- `docs/stages/011-anti-bot-modes.md`

## Future Implementation Notes

`stealth` should enable Crawl4AI's stealth browser mode and tune conservative delays. It may also need a non-headless option for sites that detect headless browsers more aggressively.

`aggressive` should build on `stealth` and add Crawl4AI proxy escalation:

- direct connection first;
- one or more configured proxies after anti-bot detection;
- retry rounds with `max_retries`;
- optional `fallback_fetch_function` for an external unlocker/fetch provider.

Likely configuration surface:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --anti-bot aggressive `
  --proxy "http://user:pass@proxy1:8080" `
  --proxy "http://user:pass@proxy2:8080"
```

An environment fallback such as `DOCHIVE_PROXIES` can be added later for CI or scheduled runs.

## How It Was Verified

- Verified the CLI help exposes `--anti-bot`.
- Verified the package compiles in the local development runtime.

## Known Limitations

- `basic` is lightweight anti-detection, not a guarantee against Cloudflare, DataDome, Akamai, or similar protections.
- `stealth` and `aggressive` are placeholders by design.
- No proxy configuration or fallback fetch provider exists yet.
