# Context Retrieval Plan

## Intent

Plan an OpenViking-inspired context layer around the documentation mirror without making vector search a requirement. The current product provides lexical `query`; this document describes planned context indexing, recursive retrieval, and optional LLM-assisted retrieval.

## Inspiration From OpenViking

OpenViking's useful principles for this project are architectural rather than strictly vector-specific:

- Filesystem paradigm: context is organized as files, folders, and stable resource identifiers.
- Tiered context loading: use lightweight abstracts first, richer overviews second, and full content only when needed.
- Directory recursive retrieval: locate relevant directories before pages, then relevant sections inside pages.
- Observable retrieval trajectory: expose why each directory, page, or section was selected.
- Context resources: treat pages, assets, links, catalogs, and diagnostics as addressable context.

The mirror already has a strong filesystem base:

- Markdown pages as full content.
- `_index.yaml` files as directory structure.
- `_catalog/pages.yaml`, `links.yaml`, `assets.yaml`, `errors.yaml`, and `sync.yaml` as global indexes.
- `_assets/` as localized resource storage.

## Proposed Context Levels

### L0 Abstract

Small summaries used for cheap routing.

Examples:

- One-line page abstract in frontmatter or `context_index.jsonl`.
- Directory abstract generated from child page titles and summaries.
- Site-level summary in `_catalog/summary.yaml`.

### L1 Overview

Structured but compact context.

Examples:

- Heading tree for a page.
- Table/image/link counts.
- Key terms and aliases.
- First-level directory overview.
- Section list with short snippets.

### L2 Details

Full source content.

Examples:

- Complete Markdown page.
- Full section body.
- Localized image path and surrounding text.
- Full catalog entry.

## Proposed Files

Start with one generated index:

```text
_catalog/context_index.jsonl
```

Possible future sidecars:

```text
_catalog/retrieval_trace.jsonl
_catalog/aliases.yaml
```

Avoid creating many sidecar files per page until the JSONL format proves insufficient.

## Context Unit Schema

Draft `context_index.jsonl` record:

```json
{
  "uri": "mirror://docs.example.com/docs/product_docs/content/deployment/profiles.md#medium-deployment-profile",
  "kind": "section",
  "level": "L2",
  "path": "docs/product_docs/content/deployment/profiles.md",
  "source_url": "https://docs.example.com/product_docs/Content/deployment/profiles.htm",
  "title": "Deployment profiles",
  "headings": [
    "Deployment profiles",
    "System component sets",
    "Medium deployment profile"
  ],
  "abstract": "Component set for a medium example documentation deployment.",
  "text": "...",
  "terms": ["backend", "frontend", "database", "deployment", "profile"],
  "links": [],
  "assets": ["_assets/images/003.png"],
  "content_hash": "sha256:..."
}
```

## Retrieval Without Vectors

### Baseline Search

Use deterministic scoring first:

- BM25 or TF-IDF-style term scoring.
- Exact phrase boosts.
- Heading and title boosts.
- Table and list boosts.
- Number and acronym boosts.
- Path and directory boosts.
- Alias expansion from a curated dictionary.

Example alias entries:

```yaml
субд:
  - rdbms
  - database
  - база данных
балансировщик:
  - load balancer
  - reverse proxy
  - nginx
очередь:
  - broker
  - message broker
  - mq
  - artemis
```

### Directory Recursive Retrieval

Search should not be a flat scan only.

Proposed flow:

1. Score directory abstracts and overviews.
2. Select candidate directories.
3. Score pages inside candidate directories.
4. Score sections/chunks inside candidate pages.
5. Optionally expand to sibling directories if confidence is low.
6. Return selected context units with trace.

### Trace

Each retrieval result should explain itself:

```json
{
  "uri": "mirror://...",
  "score": 42.5,
  "why": [
    "matched heading: Medium deployment profile",
    "matched terms: deployment, backend, database",
    "matched table rows: backend service, database"
  ]
}
```

This planned trace keeps the retrieval chain inspectable by humans and by downstream LLM agents.

## Optional LLM-Assisted Retrieval

This is planned, experimental behavior. The project should not categorically exclude LLM-based search. A hybrid design can be useful, especially for Russian documentation, domain synonyms, and queries that do not share vocabulary with the source text.

The baseline should remain deterministic, but an optional local or low-cost LLM can help with:

- Query expansion.
- Intent classification.
- Candidate directory selection.
- Candidate chunk reranking.
- Detecting weak or irrelevant lexical matches.
- Producing a search plan before retrieval.

Recommended flow:

1. Deterministic retrieval returns broad candidates.
2. Optional helper model reranks or filters candidates.
3. Final answer model receives the chosen context and retrieval trace.
4. Output includes both deterministic scores and helper-model decisions.

This gives double-checking without making retrieval entirely opaque.

Open question:

- Should the helper model run before lexical retrieval as a query planner, after retrieval as a reranker, or both?

Likely first implementation:

- Start with reranking only. It is safer because the helper model cannot hide relevant material that deterministic retrieval never collected.

## Image Handling

The mirror pipeline should not require a VLM during crawl or index generation.

Default behavior:

- Localize images.
- Preserve source URL and local path.
- Store dimensions.
- Associate images with the surrounding page and heading.
- Use `alt` text, filenames, and nearby Markdown as searchable text.

Optional behavior:

- A multimodal model may be used at answer time or through an explicit enrichment command.
- Generated image descriptions should be stored as auditable sidecar context only when requested.
- The provenance of image descriptions must remain clear.

Open question:

- Should image interpretation be an `enrich-images` command, an on-demand `ask` behavior, or both?

Likely first implementation:

- Keep image interpretation out of `mirror` and `index`.
- Add on-demand multimodal interpretation later, scoped to images selected by retrieval.

## Proposed Future Commands

```powershell
dochive index --root .\mirror\docs.example.com
dochive retrieve --root .\mirror\docs.example.com --text "medium deployment profile" --format json --trace
dochive ask --root .\mirror\docs.example.com --text "medium deployment profile"
```

Optional later:

```powershell
dochive retrieve --root .\mirror\docs.example.com --text "..." --llm-rerank
dochive enrich-images --root .\mirror\docs.example.com --scope selected
```

## TUI Position

TUI is valuable after the context layer stabilizes.

Best TUI surfaces:

- Browse mirror tree.
- Inspect `_catalog/errors.yaml`.
- Preview `context_index.jsonl`.
- Run retrieval queries.
- View retrieval trace.
- Compare deterministic and LLM-assisted retrieval.

The TUI should remain a client of stable CLI commands, not the place where retrieval logic is first implemented.

## Recommended Implementation Order

1. Build `context_index.jsonl` from Markdown and catalogs.
2. Add heading-aware section chunking.
3. Add deterministic `retrieve --format json --trace`.
4. Add alias expansion and structural scoring.
5. Add an evaluation set of representative questions.
6. Add optional LLM reranking.
7. Add optional multimodal image interpretation.
8. Add TUI for browsing, diagnostics, and retrieval trace inspection.
