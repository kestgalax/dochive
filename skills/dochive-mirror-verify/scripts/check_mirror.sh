#!/usr/bin/env bash
# Verify a Dochive mirror: placeholders, catalog errors, live-site link leaks.
# Usage: check_mirror.sh --root MIRROR_SITE_ROOT --source-host www.example.com

set -eo pipefail

ROOT=""
SOURCE_HOST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --source-host)
      SOURCE_HOST="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: check_mirror.sh --root MIRROR_SITE_ROOT --source-host HOSTNAME"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ROOT" || -z "$SOURCE_HOST" ]]; then
  echo "Usage: check_mirror.sh --root MIRROR_SITE_ROOT --source-host HOSTNAME" >&2
  exit 2
fi

if [[ ! -d "$ROOT" ]]; then
  echo "Mirror root not found: $ROOT" >&2
  exit 2
fi

CATALOG="${ROOT}/_catalog"
if [[ ! -d "$CATALOG" ]]; then
  echo "Missing _catalog under: $ROOT" >&2
  exit 2
fi

python3 - "$ROOT" "$SOURCE_HOST" "$CATALOG" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
source_host = sys.argv[2].lower().strip()
catalog = Path(sys.argv[3])


def count_placeholders_in_yaml(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"placeholder:\s*true\b", text, flags=re.IGNORECASE))


def count_catalog_errors(catalog_dir: Path) -> int:
    path = catalog_dir / "errors.yaml"
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    # List items under errors: with a kind field.
    return len(re.findall(r"^\s*-\s+kind:\s*", text, flags=re.MULTILINE))


def count_unresolved_from_summary(catalog_dir: Path) -> int:
    path = catalog_dir / "summary.yaml"
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    match = re.search(r"links_internal_unresolved:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    unresolved_block = re.search(
        r"unresolved_internal_links:\s*\n((?:\s+-\s+.+\n)*)",
        text,
    )
    if unresolved_block:
        return len(re.findall(r"^\s+-\s+", unresolved_block.group(1), flags=re.MULTILINE))
    return 0


def count_link_leaks(root: Path, host: str) -> list[str]:
    host_pat = re.escape(host.lower())
    link_re = re.compile(
        rf"\]\(\s*https?://(?:[^/\s]*\.)?{host_pat}[^)\s]*\s*\)",
        re.IGNORECASE,
    )
    leaks: list[str] = []
    for md in root.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text
        for line_no, line in enumerate(body.splitlines(), start=1):
            if "Источник:" in line or "source_url:" in line:
                continue
            if link_re.search(line):
                leaks.append(f"{md.relative_to(root)}:{line_no}")
    return leaks


placeholder_count = sum(
    count_placeholders_in_yaml(catalog / name) for name in ("structure.yaml", "pages.yaml")
)
error_count = count_catalog_errors(catalog)
unresolved_count = count_unresolved_from_summary(catalog)
link_leaks = count_link_leaks(root, source_host)

status = "ok"
issues: list[str] = []
if placeholder_count > 0:
    status = "needs_mirror"
    issues.append(f"placeholders={placeholder_count}")
if error_count > 0:
    status = "errors" if status == "ok" else status
    issues.append(f"catalog_errors={error_count}")
if link_leaks:
    status = "link_leaks" if status == "ok" else status
    issues.append(f"live_doc_link_leaks={len(link_leaks)}")
if unresolved_count > 0:
    issues.append(f"unresolved_internal_links={unresolved_count}")

report = {
    "status": status,
    "mirror_root": str(root),
    "source_host": source_host,
    "placeholders": placeholder_count,
    "catalog_errors": error_count,
    "unresolved_internal_links": unresolved_count,
    "live_doc_link_leaks": len(link_leaks),
    "leak_samples": link_leaks[:10],
    "issues": issues,
}

print(json.dumps(report, ensure_ascii=False, indent=2))

exit_code = 0
if placeholder_count > 0 or error_count > 0 or link_leaks:
    exit_code = 1
sys.exit(exit_code)
PY
