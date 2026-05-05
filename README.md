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
python3 -m venv .venv
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

On macOS with Homebrew Python, install into a virtual environment as shown above. If `python3 -m pip install -e .` fails with `externally-managed-environment`, create and activate `.venv`, then use `python -m pip install -e .` inside it.

If `.venv` was created before switching Python installers, recreate it with Homebrew `python3` or check `.venv/bin/python -c "import ssl; print(ssl.get_default_verify_paths())"` before diagnosing HTTPS asset failures.

## Usage

Mirror local HTML:

```bash
dochive mirror --source ./site-html --out ./mirror --max-depth 3 --save-assets images,files
```

For web crawling, install the optional Crawl4AI extra and Playwright browsers:

```bash
python -m pip install -e ".[crawl4ai]"
playwright install chromium
dochive structure --source https://docs.example.com --out ./mirror --max-depth 3
dochive mirror --source https://docs.example.com --out ./mirror --render-js
```

`dochive structure` saves `_catalog/structure.yaml` with the known navigation tree and final Gramax paths. Later `mirror` runs reuse that structure, keeping placeholders stable until each section is mirrored.

During development, editable installation keeps the `dochive` console command pointed at the current `src/` code. You can also run the package module directly from the repository root:

```bash
python -m dochive --help
```

If HTTPS asset downloads fail with `CERTIFICATE_VERIFY_FAILED`, make sure the crawl runs with a Python environment that has CA certificates configured. A fresh `.venv` created from Homebrew `python3` usually inherits the Homebrew certificate bundle; the python.org macOS installer can also be fixed with `/Applications/Python 3.x/Install Certificates.command`.

## Project Docs

- [Roadmap](docs/ROADMAP.md)
- [Usage](docs/USAGE.md)
- [Stage artifacts](docs/stages/)
