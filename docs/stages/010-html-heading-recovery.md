# Stage 10. HTML Heading Recovery

Status: completed

## Intent

Preserve the article hierarchy when documentation generators encode headings in non-standard or tool-specific HTML. The motivating Example Docs page used normal `h2` elements with MadCap autonumber spans and lower-level headings as styled paragraphs.

## Changes

- Treat `p` and `div` elements with classes `H1` through `H6` as headings in the local HTML parser.
- Extract source headings from web HTML before Markdown cleanup.
- Promote Markdown lines that exactly match source HTML headings.
- Insert missing source HTML headings before nearby recovered content anchors when Crawl4AI omits the heading text from Markdown entirely.
- Prefer the full Crawl4AI `html` field over `cleaned_html` for heading recovery because `cleaned_html` can omit MadCap `h2 data-mc-autonum` elements.
- Compare heading and anchor text after mojibake repair so generated Markdown can still be fixed when Crawl4AI returns mojibake text before normal cleanup.

## Files Touched

- `src/dochive/html_extract.py`
- `src/dochive/web_source.py`
- `mirror/docs.example.com/docs/product_docs/content/deployment/profiles.md`
- `README.md`
- `docs/USAGE.md`
- `docs/ROADMAP.md`

## Verification

- `python -m compileall src/dochive`
- Ordinary web mirror smoke test without `--content-selector`:
  - `--max-depth 0`
  - `--max-pages 1`
- Verified generated `profiles.md` contains:
  - `# Deployment profiles`
  - `## System component types`
  - `## Recommended component sets`
  - nested `#### Deployment profile ...` headings
- Verified the page still has the expected tables and images.
- Verified no headings are emitted with double spaces after `#`.

## Known Limitations

Heading insertion is intentionally conservative. A heading is inserted only when it exists in source HTML and a nearby content anchor can be found in the generated Markdown. If an extractor removes both the heading and all nearby anchor text, the tool will not guess a location.

The recovery logic handles class names that are exactly tokenized as `H1` through `H6`. Other site-specific heading class names should be added deliberately after inspecting the source HTML.
