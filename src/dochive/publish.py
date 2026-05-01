from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    output: str


def publish_mirror(root: Path, *, message: str, dry_run: bool = False, init: bool = False, push: bool = False) -> PublishResult:
    root = root.resolve()
    if not root.exists():
        return PublishResult(False, f"Root does not exist: {root}")

    lines: list[str] = []
    if not _is_git_worktree(root):
        if not init:
            return PublishResult(False, f"Not a Git worktree: {root}. Re-run with --init or initialize Git manually.")
        if dry_run:
            lines.append(f"Would run: git -C {root} init")
            lines.append(f"Would run: git -C {root} add -A")
            lines.append(f"Would run: git -C {root} commit -m {message!r}")
            if push:
                lines.append(f"Would run: git -C {root} push")
            return PublishResult(True, "\n".join(lines))
        else:
            result = _run_git(root, "init")
            lines.append(result.stdout.strip() or result.stderr.strip())
            if result.returncode != 0:
                return PublishResult(False, "\n".join(lines))

    status = _run_git(root, "status", "--short")
    if status.returncode != 0:
        return PublishResult(False, status.stderr.strip() or status.stdout.strip())
    status_text = status.stdout.strip()
    lines.append("Status:")
    lines.append(status_text or "  clean")

    if not status_text:
        return PublishResult(True, "\n".join(lines))

    if dry_run:
        lines.append(f"Would run: git -C {root} add -A")
        lines.append(f"Would run: git -C {root} commit -m {message!r}")
        if push:
            lines.append(f"Would run: git -C {root} push")
        return PublishResult(True, "\n".join(lines))

    add = _run_git(root, "add", "-A")
    if add.returncode != 0:
        return PublishResult(False, add.stderr.strip() or add.stdout.strip())

    commit = _run_git(root, "commit", "-m", message)
    lines.append(commit.stdout.strip() or commit.stderr.strip())
    if commit.returncode != 0:
        return PublishResult(False, "\n".join(lines))

    if push:
        push_result = _run_git(root, "push")
        lines.append(push_result.stdout.strip() or push_result.stderr.strip())
        if push_result.returncode != 0:
            return PublishResult(False, "\n".join(lines))

    return PublishResult(True, "\n".join(lines))


def _is_git_worktree(root: Path) -> bool:
    result = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
