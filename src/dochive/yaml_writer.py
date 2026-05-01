from __future__ import annotations

from collections.abc import Mapping, Sequence


def dumps_yaml(value: object, indent: int = 0) -> str:
    lines: list[str] = []
    _write_value(lines, value, indent)
    return "\n".join(lines).rstrip() + "\n"


def _write_value(lines: list[str], value: object, indent: int) -> None:
    prefix = " " * indent
    if isinstance(value, Mapping):
        if not value:
            lines.append(prefix + "{}")
            return
        for key, child in value.items():
            if _is_scalar(child):
                lines.append(f"{prefix}{key}: {_format_scalar(child)}")
            else:
                lines.append(f"{prefix}{key}:")
                _write_value(lines, child, indent + 2)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if not value:
            lines.append(prefix + "[]")
            return
        for child in value:
            if _is_scalar(child):
                lines.append(f"{prefix}- {_format_scalar(child)}")
            else:
                lines.append(f"{prefix}-")
                _write_value(lines, child, indent + 2)
        return
    lines.append(prefix + _format_scalar(value))


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _format_scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
