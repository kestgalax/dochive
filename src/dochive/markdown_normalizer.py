from __future__ import annotations

import re

from .text_utils import repair_mojibake


DEFAULT_NOISE_LINES = {
    "* * *",
    "Account",
    "Settings",
    "Logout",
    "Submit Search",
    "Filter:",
    "* Все разделы",
    "Skip To Main Content",
}


def normalize_markdown(markdown: str, *, clean: bool = True, extra_noise_lines: tuple[str, ...] = ()) -> str:
    text = repair_mojibake(markdown)
    text = _normalize_nbsp(text)
    text = _normalize_blank_lines(text)
    if clean:
        text = _drop_noise_lines(text, DEFAULT_NOISE_LINES | set(extra_noise_lines))
        text = _trim_leading_page_chrome(text)
        text = _drop_footer_chrome(text)
        text = _collapse_repeated_lines(text)
        text = _normalize_blank_lines(text)
    return text.strip() + "\n"


def _normalize_nbsp(text: str) -> str:
    return text.replace("\xa0", " ")


def _normalize_blank_lines(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                compact.append("")
            blank = True
        else:
            compact.append(line)
            blank = False
    return "\n".join(compact).strip()


def _drop_noise_lines(text: str, noise_lines: set[str]) -> str:
    output: list[str] = []
    for line in text.splitlines():
        normalized = _line_text(line)
        if normalized in noise_lines:
            continue
        output.append(line)
    return "\n".join(output)


def _collapse_repeated_lines(text: str) -> str:
    output: list[str] = []
    previous = ""
    repeat_count = 0
    for line in text.splitlines():
        normalized = _line_text(line)
        if normalized and normalized == previous:
            repeat_count += 1
            if repeat_count >= 1:
                continue
        else:
            repeat_count = 0
        output.append(line)
        previous = normalized
    return "\n".join(output)


def _trim_leading_page_chrome(text: str) -> str:
    lines = text.splitlines()
    heading_index = _first_h1_index(lines)
    if heading_index is None or heading_index == 0:
        return text

    keep_from = heading_index
    previous_index = _previous_nonblank_index(lines, heading_index)
    if previous_index is not None and _looks_like_breadcrumb(lines[previous_index]):
        keep_from = previous_index

    if _looks_like_navigation_chrome(lines[:keep_from]):
        return "\n".join(lines[keep_from:])
    return text


def _first_h1_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if re.match(r"^#\s+\S", line.strip()):
            return index
    return None


def _previous_nonblank_index(lines: list[str], before: int) -> int | None:
    for index in range(before - 1, -1, -1):
        if lines[index].strip():
            return index
    return None


def _looks_like_breadcrumb(line: str) -> bool:
    normalized = _line_text(line)
    return " > " in normalized and ("[" in normalized or "](" in normalized)


def _looks_like_navigation_chrome(lines: list[str]) -> bool:
    nonblank = [_line_text(line) for line in lines if line.strip()]
    if not nonblank:
        return False
    link_lines = sum(1 for line in nonblank if "](" in line)
    list_lines = sum(1 for line in nonblank if line.startswith(("* ", "- ")))
    has_skip_or_logo = any("Skip To Main Content" in line or "transparent" in line for line in nonblank)
    return has_skip_or_logo or link_lines >= 5 or list_lines >= 5


def _drop_footer_chrome(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        normalized = _line_text(line)
        if (
            "Обращаем ваше внимание" in normalized
            or "публичной оферт" in normalized
            or "ctrl+enter" in normalized
        ):
            start = _footer_start_index(lines, index)
            return "\n".join(lines[:start])
    return text


def _footer_start_index(lines: list[str], index: int) -> int:
    for candidate in range(index - 1, max(index - 4, -1), -1):
        normalized = _line_text(lines[candidate])
        if "Страница продукта" in normalized or "products/service_desk_pro" in normalized:
            return candidate
    return index


def _line_text(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\s*[-*]\s+", "* ", line)
    line = re.sub(r"\s+", " ", line)
    return line
