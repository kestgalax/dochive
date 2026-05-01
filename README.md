# Dochive

CLI tool for mirroring HTML documentation into a Markdown-first repository:

- Markdown page files with YAML frontmatter
- `_index.yaml` in every folder
- global `_catalog/*.yaml` files
- deterministic URL/file mapping
- optional Crawl4AI web crawling
- local HTML folder mirroring without browser dependencies
- recovery for documentation headings written as styled HTML, such as `p class="H4"` or MadCap `h2 data-mc-autonum`

## Usage

```powershell
dochive mirror --source .\site-html --out .\mirror --max-depth 3 --save-assets images,files
```

Or with the bundled Python during development:

```powershell
C:\Users\me\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m dochive mirror --source .\site-html --out .\mirror
```

Prefer the `python -m dochive ...` form during development if you are editing `src/` directly. A previously installed `dochive` console script may point at an older package until it is reinstalled.

For web crawling, install the optional Crawl4AI extra and run:

```powershell
dochive mirror --source https://docs.example.com --out .\mirror --render-js
```

On this Codex desktop runtime, the console script is installed outside PATH. Use:

```powershell
$env:PATH = "C:\Users\me\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Scripts;$env:PATH"
```

Then `dochive ...` works in the current PowerShell session.

## Project Docs

- [Roadmap](docs/ROADMAP.md)
- [Usage](docs/USAGE.md)
- [Stage artifacts](docs/stages/)
