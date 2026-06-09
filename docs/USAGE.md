# Dochive Usage

[Русский](USAGE.ru.md) | [English](USAGE.md)

## Requirements

- Python 3.10 or newer
- Git, only for source checkout or `dochive publish`
- Optional: Crawl4AI dependencies for JavaScript-rendered web crawling

Dochive is a Python package with a `dochive` console command. The recommended setup is the same on Windows, Linux, and macOS: create a virtual environment, install the package, then run `dochive`.

## Install From Source

Clone the repository:

```bash
git clone https://github.com/kestgalax/dochive.git
cd dochive
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Upgrade `pip` and install Dochive in editable mode:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Verify the CLI is available:

```bash
dochive --help
```

During development, editable installation keeps the `dochive` command pointed at the current `src/` code. You can also run the package module directly from the repository root:

```bash
python -m dochive --help
```

## Command Overview

Dochive exposes six commands:

- `dochive mirror`: mirror a URL, local HTML file, or local HTML directory into Markdown and YAML catalogs.
- `dochive structure`: discover and save a web navigation structure before content mirroring.
- `dochive relink`: rewrite external Markdown links to internal paths in an existing mirror without re-crawling.
- `dochive catalog`: print the expected catalog file paths for a mirror.
- `dochive query`: run lexical search over mirrored Markdown and YAML files.
- `dochive publish`: commit and optionally push a mirror directory with Git.

### macOS Homebrew Python

Homebrew Python does not allow package installs into the global interpreter. If `python3 -m pip install -e .` fails with `externally-managed-environment`, create a virtual environment first:

```bash
cd dochive
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m dochive --help
```

After activation, `python` points to `.venv/bin/python`, so use `python -m dochive ...` for mirror commands in that shell.

If `.venv` already exists and was created with another Python installer, check it before troubleshooting HTTPS errors:

```bash
.venv/bin/python -c "import ssl, sys; print(sys.executable); print(ssl.get_default_verify_paths())"
```

If `cafile=None`, recreate the environment with Homebrew Python or reinstall Dochive after updating this project version.

## Optional Web Crawling Dependencies

Local HTML mirroring does not need browser dependencies. For JavaScript-rendered web documentation, install the optional Crawl4AI extra:

```bash
python -m pip install -e ".[crawl4ai]"
```

After installing Crawl4AI, download the Playwright browser binaries:

```bash
playwright install chromium
```

For all browsers (Chromium, Firefox, WebKit):

```bash
playwright install
```

Then run web crawls with `--render-js`. Local HTML mirroring still works without Crawl4AI.

Dochive sets workspace-local Crawl4AI defaults during web crawling. If you call Crawl4AI tools directly, you may set these variables yourself.

Windows PowerShell:

```powershell
$env:CRAWL4_AI_BASE_DIRECTORY = "$PWD\.crawl4ai-data"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
$env:PYTHONIOENCODING = "utf-8"
```

Linux or macOS:

```bash
export CRAWL4_AI_BASE_DIRECTORY="$PWD/.crawl4ai-data"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-browsers"
export PYTHONIOENCODING="utf-8"
```

## Discover Web Structure

For web documentation with a stable navigation tree, build the structure before mirroring content:

```bash
dochive structure \
  --source "https://docs.example.com/start.htm" \
  --out ./mirror \
  --max-depth 3 \
  --scope subtree \
  --structure-mode auto
```

The command writes `_catalog/structure.yaml` under the mirror root. It stores known source URLs, navigation paths, parent links, order, placeholder status, and final Gramax paths. Later runs of `dochive mirror` against the same output directory reuse this file: missing pages remain placeholders, and separately mirrored sections fill the existing paths instead of creating a second layout.

`--structure-mode auto` is best for known documentation engines. For MadCap WebHelp, it detects navigation from `Data/HelpSystem.xml` and its TOC chunks when available. For Wiki.js-style sites, it falls back to link-based discovery and applies Wiki-friendly URL and cleanup rules for extensionless pages, language prefixes, service links, permalink heading anchors, and repeated site chrome.

Use `--structure-mode toc` to require a MadCap TOC, or `--structure-mode links` to use link-based discovery directly. In TOC mode, `--scope subtree` means the selected user-visible TOC branch, not just the URL directory.

Use `--include-url-prefix` when a documentation branch legitimately links outside the selected subtree but should still be eligible:

```bash
dochive structure \
  --source "https://docs.example.com/product/start.htm" \
  --out ./mirror \
  --scope subtree \
  --include-url-prefix "https://docs.example.com/shared/"
```

For a focused Wiki.js subtree, start from the actual language-prefixed page and keep `--scope subtree`:

```bash
dochive mirror \
  --source "https://wiki.example.com/ru/advices" \
  --out ./mirror \
  --render-js \
  --max-depth 10 \
  --max-pages 1000 \
  --scope subtree \
  --structure-mode auto \
  --save-assets images
```

For protected Confluence Server/Data Center pages with Resolution API Token Authentication, use the isolated Confluence source type. The bearer token is read from `.env` or the process environment and is also used for protected asset downloads:

```bash
cp .env.example .env
# edit .env and set DOCHIVE_AUTH_TOKEN
dochive mirror \
  --source "https://wiki.example.com/pages/viewpage.action?pageId=123" \
  --out ./mirror \
  --render-js \
  --source-type confluence \
  --auth bearer \
  --scope subtree \
  --save-assets images
```

## Mirror Local HTML

Examples below use PowerShell line continuations. On Linux or macOS, use the same options in one line or replace trailing backticks with `\`.

```powershell
dochive mirror `
  --source .\examples\local-html `
  --out .\mirror-test `
  --max-depth 3 `
  --save-assets images
```

`--source` may point to either a directory or a single `.html`/`.htm` file. Local mirroring uses the filesystem and does not require `--render-js`.

## Mirror A Web Documentation Subtree

**macOS / Linux:**

```bash
dochive mirror \
  --source "url" \
  --out ./mirror \
  --render-js \
  --max-depth 1 \
  --max-pages 20 \
  --scope subtree \
  --structure-mode auto \
  --save-assets images \
  --image-size-mode max-width \
  --image-max-width 900
```

**Windows PowerShell:**

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --max-depth 1 `
  --max-pages 20 `
  --scope subtree `
  --structure-mode auto `
  --save-assets images `
  --image-size-mode max-width `
  --image-max-width 900
```

Use `--scope subtree` for a controlled crawl. Use `--scope domain` only when you intentionally want the whole domain to be eligible.
For focused crawls that need shared assets or a common pages directory, add one or more `--include-url-prefix` values.

## Relink Internal Markdown Links

During incremental mirroring, an already mirrored page may still contain absolute URLs to other documentation pages that were mirrored later or are only known from `_catalog/structure.yaml`. `dochive relink` fixes those links offline: it reads the full URL-to-path map from `structure.yaml` and `pages.yaml`, rewrites Markdown bodies, and updates catalog metadata without a new crawl.

Typical workflow:

1. Run `dochive structure` once for the mirror root.
2. Mirror documentation sections with repeated `dochive mirror` runs.
3. Run `dochive relink --root ./mirror/www.example.com` after each major incremental batch.

```bash
dochive relink --root ./mirror/www.example.com
```

Useful options:

- `--dry-run`: report how many pages would change without writing files.
- `--path-prefix docs/route`: relink only pages under one mirror-relative subtree.

`structure.yaml` is required for links to pages that are not mirrored yet but already have a planned Gramax path. Without it, `relink` can only resolve URLs already present in `pages.yaml`.

## Output Layout

Dochive writes nested pages in the layout expected by Gramax. When a crawled page has child pages, the page becomes a folder and the original page content is written to `_index.md`; pages without children stay as regular Markdown files.

Before child pages are known, a page path would look flat:

```text
docs/product_docs/content/release_notes/version_35.md
```

With crawled children, the generated mirror becomes:

```text
docs/product_docs/content/release_notes/version_35/_index.md
docs/product_docs/content/release_notes/version_35/known_issues.md
docs/product_docs/content/release_notes/archive.md
```

Internal Markdown links, page frontmatter, `_catalog/*.yaml`, sync reports, and folder `_index.yaml` files all use the final `_index.md` paths. Page frontmatter also receives `order` based on the source navigation order, so Gramax can sort sibling pages the same way as the original documentation.

Use `--save-assets images` when screenshots must be copied locally and Markdown image links must point to page-local media, such as `./example.png` from a Gramax `_index.md` page.

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

## Image Output

By default, linked screenshots are written in Gramax image form:

```html
<image src="./example.png" crop="0,0,100,100" scale="100" width="1427px" height="617px" float="center"/>
```

The default `--image-size-mode intrinsic` reads the real downloaded image dimensions and writes them into the Gramax image tag. Saved media is stored next to the Markdown page: regular `version_35.md` pages use `version_35/`, while Gramax head pages use the same folder as `version_35/_index.md`.

By default, images at or below `--image-inline-max-px 52` (for example MadCap list icons) use `float="left"` and omit the `scale` attribute instead of centered block `<image>` tags that Gramax would upscale. Every Gramax `<image>` tag is written as a separate block with a blank line before and after, never inside a bullet line or inline with sentence text. List text that belonged to the same item is written after the image block, usually as `* ...`.

For wide screenshots, cap rendered width while preserving aspect ratio:

```powershell
--image-size-mode max-width --image-max-width 900
```

This emits responsive HTML like:

```html
<image src="./example.png" crop="0,0,100,100" scale="63" width="900px" height="389px" float="center"/>
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

HTML `<video>` blocks are preserved in Markdown as Gramax video tags:

```html
<video path="./release_notes_video/example.mp4"/>
```

Without asset saving, video tags keep the original remote URL. To copy MP4 sources from HTML `<video>` blocks into the mirror and rewrite video `path` attributes to the page-local media folder, include `videos` in `--save-assets`:

```powershell
dochive mirror `
  --source "url" `
  --out .\mirror `
  --render-js `
  --save-assets images,videos
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

By default, cleanup also trims repeated page chrome before the first article heading and removes generic legal/footer/support-feedback blocks. Site-wide navigation remains available through `_index.yaml` and `_catalog/*.yaml`; it is not duplicated inside every Markdown article.

## Heading Recovery

Some documentation generators do not express all headings as plain `h2`/`h3` elements in the Markdown produced by Crawl4AI. The mirror restores headings from the source HTML before Markdown cleanup.

Supported patterns include:

```html
<p class="H4">Supported deployment profile</p>
<h2 data-mc-autonum=""><span class="autonumber"><span></span></span>System component types</h2>
```

The web crawler uses the full HTML response for this recovery because Crawl4AI `cleaned_html` can omit some MadCap `h2 data-mc-autonum` headings. The local HTML parser also treats `p` and `div` classes named `H1` through `H6` as Markdown headings.

When Crawl4AI drops the heading text entirely, Dochive can still insert the heading before the next source paragraph or first list item when that follower text survives in Markdown.

No special CLI flag is required. If recovered headings do not appear after a normal run, first verify that the command is using the current repository code, for example with `python -m dochive ...` from the repo root.

## Inspect Catalogs

```powershell
dochive catalog --root .\mirror\docs.example.com
```

Important files:

```text
_catalog/summary.yaml
_catalog/sync.yaml
_catalog/sync_history.yaml
_catalog/structure.yaml
_catalog/pages.yaml
_catalog/links.yaml
_catalog/assets.yaml
_catalog/errors.yaml
```

Each folder also receives `_index.yaml` for deterministic hierarchy and catalog navigation. LLM-oriented retrieval is planned in the [roadmap](ROADMAP.md).

## Lexical Search

```powershell
dochive query --root .\mirror\docs.example.com --text "quick start" --limit 5
```

`dochive query` currently performs lexical file search over Markdown and YAML only. Future context indexing, recursive retrieval, vector/non-vector retrieval strategy, Telegram bot, and LLM assistant ideas are tracked in the [roadmap](ROADMAP.md).

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

If remote image downloads fail with `CERTIFICATE_VERIFY_FAILED`, Python could not verify the site's HTTPS certificate chain. Use a Python environment with CA certificates configured, for example a fresh `.venv` created from Homebrew `python3`, then reinstall Dochive inside it. For the python.org macOS installer, run the bundled `/Applications/Python 3.x/Install Certificates.command` once and retry the mirror.

## Changelog Updates

In Cursor, use the project slash command `/changelog` to turn the current chat session into bilingual `CHANGELOG.ru.md` and `CHANGELOG.md` entries. The command definition lives in `.cursor/commands/changelog.md`.

## Publish With Git

Preview the Git actions first:

```powershell
dochive publish `
  --root .\mirror\docs.example.com `
  --dry-run `
  --init `
  --message "Update documentation mirror"
```

Commit locally:

```powershell
dochive publish `
  --root .\mirror\docs.example.com `
  --init `
  --message "Update documentation mirror"
```

Push after commit only when a remote is already configured:

```powershell
dochive publish `
  --root .\mirror\docs.example.com `
  --message "Update documentation mirror" `
  --push
```
