# Stage 3. File-Based Query

Status: completed

## Intent

Add a simple lexical search command that works directly over `_catalog/pages.yaml`, `_index.yaml`, and Markdown files. This creates the base behavior for possible future bot or assistant integrations.

## Changes

- Add `dochive query`.
- Search generated `.md` and `.yaml` files under a mirror root.
- Return ranked file hits with short snippets.
- Avoid external services and vector databases.
- Prefer Markdown body snippets over YAML frontmatter snippets.

## Files Touched

- `src/dochive/search.py`
- `src/dochive/cli.py`

## Verification

- `python -m compileall src`
- `dochive query --root .\mirror-test\local-html --text install --limit 3`
- Verified the top result is `guide\install.md` with a body snippet.

## Known Limitations

The first version is lexical search only. It does not summarize answers and does not perform context indexing, recursive retrieval, vector search, or hierarchical LLM navigation; those remain roadmap items.
