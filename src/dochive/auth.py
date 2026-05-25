from __future__ import annotations

import os
import re
from pathlib import Path

from .models import MirrorConfig


def validate_auth_config(config: MirrorConfig) -> None:
    if config.auth_mode == "none":
        return
    if config.auth_mode != "bearer":
        raise RuntimeError(f"Unsupported auth mode: {config.auth_mode}")
    if config.source_type != "confluence":
        raise RuntimeError("Authentication is currently supported only with `--source-type confluence`.")
    request_headers(config)


def request_headers(config: MirrorConfig) -> dict[str, str]:
    if config.auth_mode == "none":
        return {}
    if config.auth_mode != "bearer":
        raise RuntimeError(f"Unsupported auth mode: {config.auth_mode}")
    token = _env_value(config.auth_token_env).strip()
    if not token:
        raise RuntimeError(
            f"Bearer auth requires {config.auth_token_env} to be set in the environment or a .env file."
        )
    return {"Authorization": f"Bearer {token}"}


def _env_value(name: str) -> str:
    if value := os.environ.get(name):
        return value
    return _dotenv_values().get(name, "")


def _dotenv_values(start: Path | None = None) -> dict[str, str]:
    path = _find_dotenv(start or Path.cwd())
    if path is None:
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        values[key] = _parse_dotenv_value(value)
    return values


def _find_dotenv(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def _parse_dotenv_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            inner = value[1:end]
            return bytes(inner, "utf-8").decode("unicode_escape") if quote == '"' else inner
    return value.split(" #", 1)[0].strip()
