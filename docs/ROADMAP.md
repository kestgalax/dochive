# Dochive Roadmap

## Goal

Build a CLI-first documentation mirroring tool that converts HTML documentation into a Git-friendly Markdown knowledge base with YAML metadata and file-based LLM search.

## Product Shape

The CLI should support:

```powershell
dochive mirror --source <url-or-local-html> --out .\mirror
dochive catalog --root .\mirror\<site>
dochive query --root .\mirror\<site> --text "..."
```

Optional later:

```powershell
dochive tui
```

Context/retrieval direction:

```powershell
dochive index --root .\mirror\<site>
dochive retrieve --root .\mirror\<site> --text "..." --format json --trace
dochive ask --root .\mirror\<site> --text "..."
```

See [Context Retrieval Plan](CONTEXT_RETRIEVAL_PLAN.md) for the OpenViking-inspired design notes, non-vector retrieval plan, and open questions.

## Stages

### Stage 1. Markdown Quality And Noise Filtering

Status: completed

Deliverables:

- Markdown post-normalizer.
- Basic navigation/noise line filtering.
- Crawl4AI extraction controls: content selector, exclude selector, exclude tags.
- Documentation artifact in `docs/stages/001-markdown-quality.md`.

### Stage 2. Assets And Links

Status: completed

Deliverables:

- More reliable asset downloading and local media rewrite.
- Screenshot/video/iframe metadata support.
- Broken link and unresolved asset reports.
- `_catalog/errors.yaml`.

### Stage 3. Incremental Sync

Status: completed

Deliverables:

- Previous catalog comparison.
- Changed/unchanged/deleted page detection.
- Sync report and changelog.

### Stage 4. File-Based Search

Status: completed

Deliverables:

- `query` command using `_index.yaml`, `_catalog/pages.yaml`, and plain Markdown.
- No vector database.
- Useful output for Telegram bot integration.

### Stage 5. Publish

Status: completed

Deliverables:

- Git status/add/commit helper.
- Optional remote push.
- Safe dry-run mode.

### Stage 6. TUI

Status: planned, optional

Deliverables:

- Interactive source/out configuration.
- Crawl preview.
- Progress and recent errors.
- Catalog browsing.

### Stage 7. Usage Documentation

Status: completed

Deliverables:

- PowerShell setup instructions.
- Local HTML mirroring command.
- Web subtree mirroring command.
- Selector/noise cleanup examples.
- Catalog and query commands.

### Stage 8. Media Assets

Status: completed

Deliverables:

- Extract image assets from generated Markdown.
- Localize thumbnail images.
- Localize full-size image links around thumbnails.
- Rewrite Markdown image links to `_assets/images/...`.

### Stage 9. Article Cleanup And Image Sizing

Status: completed

Deliverables:

- Trim repeated navigation/page chrome from Markdown article bodies.
- Keep global structure in YAML catalogs instead of duplicating it in every `.md`.
- Read intrinsic PNG/JPEG/GIF dimensions from localized images.
- Emit Gramax-friendly HTML image tags with size attributes.
- Optional max-width image rendering mode.

### Stage 10. HTML Heading Recovery

Status: completed

Deliverables:

- Restore headings represented as styled blocks, for example `p class="H4"` and `div class="H3"`.
- Restore MadCap headings such as `h2 data-mc-autonum` when Crawl4AI Markdown omits them.
- Use full Crawl4AI HTML for structural recovery because `cleaned_html` can drop some headings.
- Keep promotion conservative: only source-HTML headings are promoted or inserted.
- Documentation artifact in `docs/stages/010-html-heading-recovery.md`.

### Stage 11. Anti-Bot Crawl Modes

Status: completed

Deliverables:

- Add `--anti-bot off|basic|stealth|aggressive`.
- Make `basic` the default for web crawling.
- Keep `off` available for reproducible plain Crawl4AI diagnostics.
- Reserve `stealth` and `aggressive` with explicit documentation for future implementation.
- Documentation artifact in `docs/stages/011-anti-bot-modes.md`.

### Stage 12. Context Index And Recursive Retrieval

Status: planned

Deliverables:

- Build `_catalog/context_index.jsonl` from mirrored Markdown.
- Chunk pages by recovered heading hierarchy instead of fixed character windows.
- Store stable `mirror://`-style URIs, source paths, heading chains, snippets, terms, links, assets, and content hashes for each context unit.
- Add `index` command to regenerate the context index.
- Add `retrieve` command with `--format json` and optional `--trace`.
- Implement weighted lexical and structural scoring without requiring a vector database.
- Support directory-recursive retrieval: directory overview -> page -> section/chunk.
- Document the retrieval trace so an LLM or human can inspect why a context item was selected.

### Stage 13. Optional LLM-Assisted Retrieval

Status: planned, experimental

Deliverables:

- Add an optional second-stage reranker/search assistant that can use a local or low-cost LLM.
- Keep deterministic lexical/structural retrieval as the baseline and fallback.
- Allow the helper model to expand queries, select candidate directories, rerank candidate chunks, or reject weak matches.
- Return both deterministic scores and LLM-assisted decisions in retrieval trace output.
- Avoid making final answer quality depend on one opaque LLM call.

### Stage 14. Multimodal Resource Interpretation

Status: planned, optional

Deliverables:

- Keep image localization, sizing, and metadata extraction in the mirror pipeline.
- Do not require a VLM during crawling or indexing.
- Add optional multimodal interpretation for selected images when an answer model needs it.
- Store generated image descriptions as auditable sidecar context only when explicitly requested.
- Preserve asset provenance: source URL, local path, surrounding heading, and referencing page.

### Stage 15. TUI

Status: planned, optional

Deliverables:

- Interactive source/out configuration.
- Crawl preview.
- Progress and recent errors.
- Catalog browsing.
- Context index browsing.
- Retrieval trace inspection.

Notes:

- TUI should build on stable `mirror`, `index`, and `retrieve` commands rather than becoming the primary implementation surface.

## Artifact Rule

Every implemented stage must create or update a short artifact under `docs/stages/` with:

- What changed.
- Files touched.
- How it was verified.
- Known limitations.
