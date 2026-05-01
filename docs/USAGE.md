# Dochive Usage

## Setup In Current PowerShell Session

On this Codex desktop runtime, add the bundled Python scripts directory to `PATH`:

```powershell
$env:PATH = "C:\Users\me\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Scripts;$env:PATH"
```

Optional Crawl4AI runtime folders are kept inside the workspace:

```powershell
$env:CRAWL4_AI_BASE_DIRECTORY = "$PWD\.crawl4ai-data"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
$env:PYTHONIOENCODING = "utf-8"
```

The CLI sets sane defaults for these during web crawling, but setting them explicitly is useful for direct Crawl4AI commands.

During development, prefer running the package as a module from the repository root:

```powershell
C:\Users\me\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m dochive mirror --source "url" --out .\mirror
```

This guarantees the current `src/` code is used. If you run the installed `dochive` console script, reinstall the package after code changes so it does not use an older installed copy.

## Mirror Local HTML

```powershell
dochive mirror `
  --source .\examples\local-html `
  --out .\mirror-test `
  --max-depth 3 `
  --save-assets images,files
```

## Mirror A Web Documentation Subtree
Example 1:
```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --max-depth 1 `
  --max-pages 20 `
  --scope subtree `
  --save-assets images
```
Example 2:
```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --max-depth 1 `
  --max-pages 20 `
  --scope subtree `
  --save-assets images `
  --image-size-mode max-width `
  --image-max-width 900
```

Use `--scope subtree` for a controlled crawl. Use `--scope domain` only when you intentionally want the whole domain to be eligible.

Use `--save-assets images` when screenshots must be copied locally and Markdown image links must point to `_assets/images/...`.

## Anti-Bot Modes

Web crawling uses `--anti-bot basic` by default. This keeps the browser headless, but asks Crawl4AI to randomize the user agent and apply lightweight page interaction and navigator overrides:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --anti-bot basic
```

Use `--anti-bot off` when you need the older plain Crawl4AI behavior for diagnostics or reproducibility.

Reserved modes:

- `--anti-bot stealth`: planned to enable Crawl4AI stealth mode and tune delays for protected sites.
- `--anti-bot aggressive`: planned to add proxy escalation, retry rounds, and optional fallback fetch providers.

These reserved modes are accepted by the CLI choices, but intentionally stop with a clear error until the required runtime configuration is implemented. Aggressive mode will need a proxy list, probably through `--proxy` and/or a `DOCHIVE_PROXIES` environment variable, plus an optional fallback fetch provider for sites that block all browser attempts.

By default, linked screenshots are written in a Gramax-friendly HTML form:

```html
<img src="../../../../../_assets/images/example.png" alt="" width="1427" height="617" />
```

The default `--image-size-mode intrinsic` reads the real downloaded image dimensions and writes them into the HTML tag.

For wide screenshots, cap rendered width while preserving aspect ratio:

```powershell
--image-size-mode max-width --image-max-width 900
```

This emits responsive HTML like:

```html
<img src="../../../../../_assets/images/example.png" alt="" width="900" height="389" style="max-width: 100%; height: auto;" />
```

Disable image size attributes only for diagnostics:

```powershell
--image-size-mode none
```

Use Markdown image output only when you explicitly need it:

```powershell
--image-render-mode markdown
```

Use `--image-link-mode linked` only when you explicitly need standard Markdown linked images:

```markdown
[![](thumb.png)](full.png)
```

## Mirror Videos

HTML `<video>` blocks are preserved in Markdown as playable HTML:

```html
<video controls src="../../../../../_assets/videos/example.mp4"></video>
```

Without asset saving, video tags keep the original remote URL. To copy MP4 files into the mirror and rewrite video `src` attributes to `_assets/videos/...`, include `videos` in `--save-assets`:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --save-assets images,videos,files
```

## Improve Extraction With Selectors

If a documentation site has a stable content container, prefer narrowing extraction:

```powershell
dochive mirror `
  --source "https://docs.example.com/start.html" `
  --out .\mirror `
  --render-js `
  --content-selector "main" `
  --exclude-selector ".sidebar,.topbar,.search"
```

You can also remove exact noisy Markdown lines:

```powershell
dochive mirror `
  --source .\site-html `
  --out .\mirror `
  --noise-line "Account" `
  --noise-line "Logout"
```

Disable cleanup only for diagnostics:

```powershell
dochive mirror --source .\site-html --out .\mirror --no-clean-markdown
```

By default, cleanup also trims repeated page chrome before the first article heading and removes the Naumen legal footer. Site-wide navigation remains available through `_index.yaml` and `_catalog/*.yaml`; it is not duplicated inside every Markdown article.

## Heading Recovery

Some documentation generators do not express all headings as plain `h2`/`h3` elements in the Markdown produced by Crawl4AI. The mirror restores headings from the source HTML before Markdown cleanup.

Supported patterns include:

```html
<p class="H4">Типовая конфигурация до 500 одновременных пользователей (sd_pro_small)</p>
<h2 data-mc-autonum=""><span class="autonumber"><span></span></span>Типы компонентов систем SD Pro</h2>
```

The web crawler uses the full HTML response for this recovery because Crawl4AI `cleaned_html` can omit some MadCap `h2 data-mc-autonum` headings. The local HTML parser also treats `p` and `div` classes named `H1` through `H6` as Markdown headings.

No special CLI flag is required. If recovered headings do not appear after a normal run, first verify that the command is using the current repository code, for example with `python -m dochive ...` from the repo root.

## Inspect Catalogs

```powershell
dochive catalog --root .\mirror\www.naumen.ru
```

Important files:

```text
_catalog/summary.yaml
_catalog/sync.yaml
_catalog/sync_history.yaml
_catalog/pages.yaml
_catalog/links.yaml
_catalog/assets.yaml
_catalog/errors.yaml
```

Each folder also receives `_index.yaml` for hierarchical LLM navigation.

## Search Without Vectors

```powershell
dochive query --root .\mirror\www.naumen.ru --text "быстрый старт" --limit 5
```

This performs lexical file search over Markdown and YAML. It is the first retrieval layer for a future Telegram bot or LLM assistant.

## Inspect Incremental Sync

Repeated runs compare the new page content hashes with the previous `_catalog/pages.yaml` and write:

```text
_catalog/sync.yaml
_catalog/sync_history.yaml
```

`sync.yaml` contains the latest run. `sync_history.yaml` appends every run as a separate YAML document so repeated mirrors of the same site remain inspectable over time.

Each report includes:

- `added`
- `changed`
- `unchanged`
- `deleted`

The same counts are also embedded in `_catalog/summary.yaml`.

## Inspect Errors And Warnings

Diagnostics are written to:

```text
_catalog/errors.yaml
```

Typical warnings:

- unresolved internal links because `--max-depth` or `--max-pages` was too low;
- missing local HTML links;
- missing or failed assets.

## Publish With Git

Preview the Git actions first:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --dry-run `
  --init `
  --message "Update documentation mirror"
```

Commit locally:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --init `
  --message "Update documentation mirror"
```

Push after commit only when a remote is already configured:

```powershell
dochive publish `
  --root .\mirror\www.naumen.ru `
  --message "Update documentation mirror" `
  --push
```
