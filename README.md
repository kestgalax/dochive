# Dochive

CLI tool for mirroring HTML documentation into a Markdown-first repository:

- Markdown page files with YAML frontmatter
- `_index.yaml` in every folder
- global `_catalog/*.yaml` files
- deterministic URL/file mapping
- optional Crawl4AI web crawling
- local HTML folder mirroring without browser dependencies
- recovery for documentation headings written as styled HTML, such as `p class="H4"` or MadCap `h2 data-mc-autonum`

## Install

Dochive requires Python 3.10 or newer.

```bash
git clone https://github.com/kestgalax/dochive.git
cd dochive
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Install the package:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
dochive --help
```

## Usage

Mirror local HTML:

```bash
dochive mirror --source ./site-html --out ./mirror --max-depth 3 --save-assets images,files
```

For web crawling, install the optional Crawl4AI extra and run:

```bash
python -m pip install -e ".[crawl4ai]"
dochive mirror --source https://docs.example.com --out ./mirror --render-js
```

To try Crawl4AI's native deep crawler while keeping the default manual crawler unchanged, add `--crawl4ai-deep`.

During development, editable installation keeps the `dochive` console command pointed at the current `src/` code. You can also run the package module directly from the repository root:

```bash
python -m dochive --help
```

## Project Docs

- [Roadmap](docs/ROADMAP.md)
- [Usage](docs/USAGE.md)
- [Stage artifacts](docs/stages/)
