# Stage 12. Context Index And Retrieval MVP

## What changed

- Added `dochive index --root <mirror-root>` to generate `_catalog/context_index.jsonl`.
- Added `dochive retrieve --root <mirror-root> --text "..." --format json --trace`.
- The index stores page and heading-aware section context units with stable `mirror://...` URIs, heading chains, abstracts, searchable terms, links, assets, and content hashes.
- Retrieval is deterministic and lexical: it scores title, heading, term, text, and path matches, with optional trace reasons.

## Files touched

- `src/dochive/context.py`
- `src/dochive/cli.py`
- `tests/test_context.py`
- `README.md`
- `README.ru.md`
- `docs/USAGE.md`
- `docs/USAGE.ru.md`
- `docs/stages/012-context-index-retrieval.md`

## How it was verified

- `python -m pytest tests/test_context.py`
- `python -m pytest`

## Known limitations

- Retrieval is lexical only; no vectors or LLM reranking are used.
- Directory-recursive routing is not implemented in this MVP.
- Alias expansion and answer generation remain future work.
- Image interpretation remains out of scope; image paths and nearby text are indexed as ordinary context metadata.
