# Stage 9. Article Cleanup And Image Sizing

Status: completed

## Intent

Keep Markdown files focused on article content while preserving documentation structure in YAML catalogs. Also make image rendering more predictable in Gramax by writing dimensions from the localized source images.

## Changes

- Trim repeated site navigation before the first article heading.
- Preserve a breadcrumb line immediately before the heading when present.
- Remove the Naumen legal footer from article Markdown.
- Repair common UTF-8 mojibake before cleanup.
- Read PNG, JPEG, and GIF intrinsic dimensions from downloaded/copied image files.
- Add dimensions to generated HTML image tags.
- Add dimensions to `_catalog/assets.yaml`.
- Add `--image-size-mode intrinsic|max-width|none`.
- Add `--image-max-width <px>` for capped responsive screenshots.

## Files Touched

- `src/dochive/cli.py`
- `src/dochive/image_size.py`
- `src/dochive/markdown_normalizer.py`
- `src/dochive/models.py`
- `src/dochive/text_utils.py`
- `src/dochive/writer.py`
- `docs/USAGE.md`
- `docs/ROADMAP.md`

## Verification

- `python -m py_compile` for changed Python modules.
- Naumen QuickStart mirror regenerated with:
  - `--max-depth 1`
  - `--max-pages 20`
  - `--scope subtree`
  - `--save-assets images`
- Verified `2.md` starts with the breadcrumb and article heading instead of site navigation.
- Verified `2.md` no longer contains the Naumen legal footer.
- Verified generated image tags include intrinsic dimensions, for example:
  - `width="1427" height="617"`
- Verified max-width mode with:
  - `--image-size-mode max-width`
  - `--image-max-width 900`
- Verified max-width output scales height and adds responsive style:
  - `width="900" height="389" style="max-width: 100%; height: auto;"`
- Verified `_catalog/assets.yaml` includes `width` and `height`.

## Known Limitations

The article cleanup is heuristic. It is intentionally conservative: it trims obvious repeated page chrome before the first H1 and the known Naumen legal footer. Other documentation sites should still use `--content-selector` and `--exclude-selector` when they have stable article containers.
