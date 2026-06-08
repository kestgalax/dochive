# Agent Skills — mirroring

[English](SKILLS.md) | [Русский](SKILLS.ru.md)

Skills in [`skills/`](../skills/) help agents (Cursor, Claude Code, OpenCode, etc.) mirror documentation through Dochive safely: **from scratch**, **incremental section fill**, or **verify-only** on an existing mirror.

## Skills

| Skill | Role |
|-------|------|
| **dochive-mirror** | Preflight → pick mode → `structure` / `mirror` |
| **dochive-mirror-verify** | Catalog checks, placeholders, `sync.yaml`, link leaks |

Full workflow: [`skills/dochive-mirror/SKILL.md`](../skills/dochive-mirror/SKILL.md), examples: [`examples.md`](../skills/dochive-mirror/examples.md).

## Install

```bash
# macOS / Linux — project IDE folder
./setup.sh --target cursor --force

# Windows
setup.bat --target cursor

# Manual (Cursor)
cp -r skills/dochive-mirror .cursor/skills/
cp -r skills/dochive-mirror-verify .cursor/skills/
```

After `git pull` that changes `skills/`, **reinstall** (`--force`). `.cursor/skills/` is a copy and does not update itself.

## Invoke in chat

Skills do not auto-attach — name them explicitly:

- “Apply **dochive-mirror** for `https://…` into `./mirror`”
- “**dochive-mirror-verify** for `./mirror/www.example.com`”

## Modes (short)

| Mode | When |
|------|------|
| **Greenfield** | No `_catalog/` — `structure` then `mirror` |
| **Incremental** | Target `placeholder: true` — `mirror` only, do not rerun `structure` |
| **Refresh** | Page already mirrored, re-crawl — only with explicit approval |
| **Verify-only** | Page ready, no mirror needed — verify only |

Before any command the agent runs **preflight**: read target `pages.yaml` / frontmatter and record `counts.pages` from `summary.yaml`.

## `--out` paths (common mistake)

```text
--out ./mirror                 ← CLI argument
  └── www.example.com/         ← mirror_root (catalog, verify)
        └── _catalog/
```

- Pass **`--out ./mirror`** to `mirror` / `structure`, not `./mirror/www.example.com`.
- Use **mirror_root** for `dochive catalog --root` and verify.

## Red flags

On an **existing** MadCap mirror, do not:

- use `--structure-mode links` (bypasses TOC)
- run `dochive structure` without an explicit TOC rebuild request
- pass `--out` pointing at `mirror_root` instead of the parent directory

## Quick manual check

```bash
bash skills/dochive-mirror-verify/scripts/check_mirror.sh \
  --root ./mirror/www.example.com \
  --source-host www.example.com
```

After a partial mirror, inspect `sync.yaml`: a large `deleted` count means catalog damage.

## See also

- [USAGE.md](USAGE.md) — Dochive CLI
- [README.md](../README.md) — package install
