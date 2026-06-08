from __future__ import annotations

import re
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


def loads_yaml(text: str) -> dict[str, object]:
    lines = text.splitlines()
    value, _ = _parse_block(lines, 0, 0)
    if not isinstance(value, dict):
        return {}
    return value


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[object, int]:
    if index >= len(lines):
        return {}, index
    stripped = lines[index].strip()
    if stripped == "[]":
        return [], index + 1
    if stripped == "{}":
        return {}, index + 1
    if stripped.startswith("- "):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_mapping(lines: list[str], index: int, indent: int) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current_indent = _line_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            index += 1
            continue
        match = re.match(r"([^:]+):\s*(.*)$", line.strip())
        if not match:
            break
        key = match.group(1).strip()
        rest = match.group(2).strip()
        if rest:
            mapping[key] = _parse_scalar(rest)
            index += 1
            continue
        child_indent = current_indent + 2
        if index + 1 < len(lines) and _line_indent(lines[index + 1]) >= child_indent:
            child, index = _parse_block(lines, index + 1, child_indent)
            mapping[key] = child
            continue
        mapping[key] = None
        index += 1
    return mapping, index


def _parse_sequence(lines: list[str], index: int, indent: int) -> tuple[list[object], int]:
    items: list[object] = []
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current_indent = _line_indent(line)
        if current_indent < indent:
            break
        if not line.strip().startswith("- "):
            break
        content = line.strip()[2:].strip()
        if content:
            items.append(_parse_scalar(content))
            index += 1
            continue
        child_indent = current_indent + 2
        child, index = _parse_block(lines, index + 1, child_indent)
        items.append(child)
    return items, index


def _parse_scalar(value: str) -> object:
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


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
