#!/usr/bin/env bash

# Dochive Setup Script
# Cross-platform installer for AI IDE skills (OpenCode, Claude Code, Codex, Cursor)
# Compatible with Bash 3.2+ (macOS default)

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${SCRIPT_DIR}/skills"

# Supported IDE list
IDES=("opencode" "claude" "codex" "cursor")

# Skills to install
SKILLS=("dochive-mirror" "dochive-mirror-verify")

# Flags
FLAG_ALL=false
FLAG_GLOBAL=false
FLAG_LIST=false
FLAG_FORCE=false
FLAG_CREATE_RESULTS=false
TARGET_IDE=""

# Colors (only if terminal supports it)
if [[ -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  NC='\033[0m' # No Color
else
  RED=''
  GREEN=''
  YELLOW=''
  BLUE=''
  NC=''
fi

usage() {
  cat <<EOF
Dochive Setup — install skills for your AI IDE

Usage:
  ./setup.sh [options]

Options:
  --all                Install to all detected IDE configurations
  --global             Install to global/user configuration (~/.<ide>/skills/)
  --target <ide>       Install to specific IDE (opencode|claude|codex|cursor)
  --list               Show what would be installed without copying (dry-run)
  --force              Overwrite existing skills without prompting
  --create-results-dir Create dochive-mirror-runs/ directory
  -h, --help           Show this help message

Examples:
  ./setup.sh                    # Auto-detect IDE in current project
  ./setup.sh --all              # Install to all detected IDEs
  ./setup.sh --target claude    # Install to Claude Code only
  ./setup.sh --global           # Install to global user config
  ./setup.sh --list             # Preview what will happen
EOF
}

log_info()  { echo -e "${BLUE}[INFO]${NC} $1" >&2; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Get local directory for an IDE
get_local_dir() {
  case "$1" in
    opencode) echo ".opencode/skills" ;;
    claude)   echo ".claude/skills" ;;
    codex)    echo ".codex/skills" ;;
    cursor)   echo ".cursor/skills" ;;
    *)        echo "" ;;
  esac
}

# Get global directory for an IDE
get_global_dir() {
  case "$1" in
    opencode) echo "${HOME}/.opencode/skills" ;;
    claude)   echo "${HOME}/.claude/skills" ;;
    codex)    echo "${HOME}/.codex/skills" ;;
    cursor)   echo "${HOME}/.cursor/skills" ;;
    *)        echo "" ;;
  esac
}

# Get target directory for an IDE
get_target_dir() {
  if [[ "$FLAG_GLOBAL" == true ]]; then
    get_global_dir "$1"
  else
    echo "${SCRIPT_DIR}/$(get_local_dir "$1")"
  fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      FLAG_ALL=true
      shift
      ;;
    --global)
      FLAG_GLOBAL=true
      shift
      ;;
    --target)
      if [[ -n "${2:-}" && ! "$2" =~ ^-- ]]; then
        TARGET_IDE="$2"
        shift 2
      else
        log_error "--target requires an argument (opencode|claude|codex|cursor)"
        exit 1
      fi
      ;;
    --list)
      FLAG_LIST=true
      shift
      ;;
    --force)
      FLAG_FORCE=true
      shift
      ;;
    --create-results-dir)
      FLAG_CREATE_RESULTS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

# Check if skills source exists
if [[ ! -d "${SKILLS_DIR}" ]]; then
  log_error "Skills directory not found: ${SKILLS_DIR}"
  log_info "Make sure you run this script from the repository root."
  exit 1
fi

# Detect IDE configurations in current project
detect_local_ides() {
  local found=""
  for ide in "${IDES[@]}"; do
    local dir
    dir="$(get_local_dir "$ide")"
    if [[ -d "${SCRIPT_DIR}/${dir}" ]]; then
      if [[ -n "$found" ]]; then
        found="${found} ${ide}"
      else
        found="$ide"
      fi
    fi
  done
  echo "$found"
}

# Check if an IDE is valid
is_valid_ide() {
  local ide="$1"
  for valid in "${IDES[@]}"; do
    if [[ "$valid" == "$ide" ]]; then
      return 0
    fi
  done
  return 1
}

# Determine which IDEs to install to
determine_targets() {
  local targets=""

  if [[ -n "$TARGET_IDE" ]]; then
    if ! is_valid_ide "$TARGET_IDE"; then
      log_error "Unknown IDE: ${TARGET_IDE}"
      log_info "Supported: ${IDES[*]}"
      exit 1
    fi
    targets="$TARGET_IDE"
  else
    local detected
    detected="$(detect_local_ides)"
    if [[ -z "$detected" ]]; then
      if [[ "$FLAG_GLOBAL" == true ]]; then
        # For global install without local detection, install to all known IDEs
        targets="${IDES[*]}"
      else
        log_warn "No IDE configuration detected in current project."
        log_info "Detected IDE configs look for directories like: .opencode/, .claude/, .codex/, .cursor/"
        log_info "You can:"
        log_info "  - Run with --target <ide> to force a specific IDE"
        log_info "  - Run with --global to install to user config"
        log_info "  - Initialize your IDE config first (e.g., run opencode init, or create .claude/skills/)"
        log_info ""
        log_info "Or copy skills manually:"
        for skill in "${SKILLS[@]}"; do
          log_info "  cp -r skills/${skill} ~/.opencode/skills/  # or ~/.claude/skills/"
        done
        exit 0
      fi
    else
      if [[ "$FLAG_ALL" == true ]]; then
        targets="$detected"
      else
        # Pick the first detected one unless multiple found
        local first
        first="$(echo "$detected" | awk '{print $1}')"
        local count
        count="$(echo "$detected" | wc -w | tr -d ' ')"
        if [[ "$count" -gt 1 ]]; then
          log_warn "Multiple IDE configs detected: ${detected}"
          log_info "Use --all to install to all, or --target <ide> to pick one."
          log_info "Defaulting to first detected: ${first}"
        fi
        targets="$first"
      fi
    fi
  fi

  echo "$targets"
}

# Install a single skill to a target directory
install_skill() {
  local skill="$1"
  local target_dir="$2"
  local skill_src="${SKILLS_DIR}/${skill}"
  local skill_dst="${target_dir}/${skill}"

  if [[ ! -d "$skill_src" ]]; then
    log_warn "Skill source not found: ${skill_src}"
    return 1
  fi

  if [[ -d "$skill_dst" ]]; then
    if [[ "$FLAG_FORCE" == true ]]; then
      log_info "Overwriting existing skill: ${skill_dst}"
      rm -rf "$skill_dst"
    else
      log_warn "Skill already exists: ${skill_dst}"
      read -rp "Overwrite? [y/N]: " answer
      if [[ ! "$answer" =~ ^[Yy]$ ]]; then
        log_info "Skipping ${skill}"
        return 0
      fi
      rm -rf "$skill_dst"
    fi
  fi

  mkdir -p "$target_dir"
  cp -R "$skill_src" "$skill_dst"
  log_ok "Installed ${skill} -> ${skill_dst}"
}

# Main execution
main() {
  echo ""
  echo "=============================================="
  echo "     Dochive Skill Installer              "
  echo "=============================================="
  echo ""

  local targets
  targets="$(determine_targets)"

  if [[ -z "$targets" ]]; then
    exit 0
  fi

  # List mode
  if [[ "$FLAG_LIST" == true ]]; then
    log_info "Dry-run mode. Would install to:"
    for ide in $targets; do
      local dir
      dir="$(get_target_dir "$ide")"
      echo "  [${ide}] -> ${dir}"
      for skill in "${SKILLS[@]}"; do
        echo "    - ${skill}"
      done
    done
    exit 0
  fi

  # Perform installation
  for ide in $targets; do
    local target_dir
    target_dir="$(get_target_dir "$ide")"
    log_info "Installing to [${ide}] -> ${target_dir}"
    for skill in "${SKILLS[@]}"; do
      install_skill "$skill" "$target_dir"
    done
  done

  # Create results directory if requested
  if [[ "$FLAG_CREATE_RESULTS" == true ]]; then
    local results_dir="${SCRIPT_DIR}/dochive-mirror-runs"
    mkdir -p "$results_dir"
    log_ok "Created results directory: ${results_dir}"
  fi

  echo ""
  log_ok "Installation complete!"
  echo ""
  echo "Next steps:"
  for ide in $targets; do
    case "$ide" in
      opencode)
        echo "  - OpenCode: skills available automatically if in .opencode/skills/"
        ;;
      claude)
        echo "  - Claude Code: use /dochive-mirror or /dochive-mirror-verify to invoke"
        ;;
      codex)
        echo "  - Codex: skills loaded from .codex/skills/"
        ;;
      cursor)
        echo "  - Cursor: check .cursor/ settings for custom instructions"
        ;;
    esac
  done
  echo ""
}

main
