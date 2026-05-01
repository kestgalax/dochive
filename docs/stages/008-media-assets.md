# Stage 8. Media Assets

Status: completed

## Intent

Improve media handling for documentation pages that embed screenshots as Markdown image links and wrap thumbnails with links to full-size images.

## Changes

- Extract image assets from generated Markdown, not only Crawl4AI `media`.
- Treat linked full-size image files as assets.
- Keep deduplication by asset kind and source URL.
- Verify Naumen QuickStart `2.htm` with `--save-assets images`.

## Files Touched

- `src/dochive/media_utils.py`
- `src/dochive/web_source.py`
- `src/dochive/writer.py`
- `.gitignore`

## Verification

- `python -m compileall src`
- Local fixture smoke:
  - `dochive mirror --source examples\local-html --out .\mirror-test --max-depth 3 --save-assets images,files`
- Naumen `2.htm` targeted smoke:
  - `assets_total: 17`
  - `assets_localized: 17`
- Markdown image thumbnail URLs rewritten to `_assets/images/...`
- Markdown full-size image links rewritten to `_assets/images/...`
- Gramax-friendly image mode verified:
  - default `--image-link-mode plain`
  - default `--image-render-mode html`
  - generated Markdown contains `<img src="../../../../../_assets/images/2_01-690038081ef1.png" alt="" />`
  - generated HTML image tags are emitted as standalone HTML blocks with blank lines before and after
  - generated Markdown contains no `![...]` image syntax for localized images by default
- Main Naumen QuickStart mirror regenerated with:
  - `--max-depth 1`
  - `--max-pages 20`
  - `--scope subtree`
  - `--save-assets images`
- Verified main mirror summary:
  - `pages: 7`
  - `assets_total: 37`
  - `assets_localized: 37`

## Known Limitations

This stage focuses on image files. Video, iframe, and downloadable file metadata will be handled separately.

Gramax does not document linked-image Markdown as an image insertion format. In manual preview testing, both a relative Markdown image and an HTML `<img>` rendered inside a standalone diagnostic block. `<img src="../../../../../_assets/...">` was selected as the safer default for Gramax and is emitted as a separate block. Markdown image output can still be requested with `--image-render-mode markdown`; the old linked-image form can still be requested with `--image-link-mode linked`.
