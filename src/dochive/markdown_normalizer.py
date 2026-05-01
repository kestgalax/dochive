from __future__ import annotations

import re

from .text_utils import repair_mojibake

_COPY_CODE_CONTROL_RE = re.compile(r"^(?:\[(?:copy|copy code)\]\([^)]+\)|(?:copy|copy code))$", re.IGNORECASE)
_FENCED_CODE_RE = re.compile(r"^\s*(```|~~~)")
_RAW_HTML_EXAMPLE_RE = re.compile(
    r"^</?(?:a|br|h[1-6]|strong|em|p|div|span)\b[^>]*>(?:[^<]*</(?:a|h[1-6]|strong|em|p|div|span)>)?$",
    re.IGNORECASE,
)
_NEXT_LINK_RE = re.compile(r"^\s*(?:\\?\*\\?\*)?\s*Далее\s*>>", re.IGNORECASE)


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
    text = _fence_raw_html_examples(text)
    text = _drop_code_copy_controls(text)
    text = _drop_next_page_links(text)
    text = _normalize_media_spacing(text)
    text = _normalize_blank_lines(text)
    if clean:
        text = _drop_noise_lines(text, DEFAULT_NOISE_LINES | set(extra_noise_lines))
        text = _trim_leading_page_chrome(text)
        text = _drop_embedded_navigation_chrome(text)
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


def _fence_raw_html_examples(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    in_fence = False
    while index < len(lines):
        if _FENCED_CODE_RE.match(lines[index]):
            in_fence = not in_fence
            output.append(lines[index])
            index += 1
            continue
        if in_fence:
            output.append(lines[index])
            index += 1
            continue
        if _is_raw_html_example_line(lines[index]):
            block: list[str] = []
            while index < len(lines) and (_is_raw_html_example_line(lines[index]) or not lines[index].strip()):
                block.append(lines[index])
                index += 1
            if sum(1 for line in block if _is_raw_html_example_line(line)) >= 2:
                while block and not block[-1].strip():
                    block.pop()
                if output and output[-1].strip():
                    output.append("")
                output.append("```html")
                output.extend(block)
                output.append("```")
                continue
            output.extend(block)
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def _is_raw_html_example_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.lower().startswith(("<image ", "<video ", "<source ")):
        return False
    return bool(_RAW_HTML_EXAMPLE_RE.match(stripped))


def _drop_code_copy_controls(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    for index, line in enumerate(lines):
        if _looks_like_copy_code_control(line) and _is_adjacent_to_fenced_code(lines, index):
            continue
        output.append(line)
    return "\n".join(output)


def _drop_next_page_links(text: str) -> str:
    output: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
        if not in_fence and _NEXT_LINK_RE.match(_line_text(line)):
            continue
        output.append(line)
    return "\n".join(output)


def _normalize_media_spacing(text: str) -> str:
    output: list[str] = []
    lines = text.splitlines()
    in_fence = False
    for index, line in enumerate(lines):
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence and _is_media_line(line):
            if output and output[-1].strip():
                output.append("")
            output.append(line.strip())
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if next_line.strip():
                output.append("")
            continue
        output.append(line)
    return "\n".join(output)


def _is_media_line(line: str) -> bool:
    stripped = line.strip().lower()
    return stripped.startswith(("<image ", "<video "))


def _looks_like_copy_code_control(line: str) -> bool:
    return bool(_COPY_CODE_CONTROL_RE.match(_line_text(line)))


def _is_adjacent_to_fenced_code(lines: list[str], index: int) -> bool:
    previous_index = _nearest_nonblank_index(lines, index, -1)
    next_index = _nearest_nonblank_index(lines, index, 1)
    return (
        (previous_index is not None and _FENCED_CODE_RE.match(lines[previous_index]))
        or (next_index is not None and _FENCED_CODE_RE.match(lines[next_index]))
    )


def _nearest_nonblank_index(lines: list[str], index: int, step: int) -> int | None:
    candidate = index + step
    while 0 <= candidate < len(lines):
        if lines[candidate].strip():
            return candidate
        candidate += step
    return None


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


def _drop_embedded_navigation_chrome(text: str) -> str:
    lines = text.splitlines()
    first_h1 = _first_h1_index(lines)
    if first_h1 is None:
        return text

    chrome_marker = None
    for index in range(first_h1 + 1, len(lines)):
        normalized = _line_text(lines[index])
        if "Skip To Main Content" in normalized or "transparent" in normalized:
            chrome_marker = index
            break
    if chrome_marker is None:
        return text

    next_h1 = None
    for index in range(chrome_marker + 1, len(lines)):
        if re.match(r"^#\s+\S", lines[index].strip()):
            next_h1 = index
            break
    if next_h1 is None:
        return text

    if not _looks_like_navigation_chrome(lines[first_h1:next_h1]):
        return text

    keep_from = next_h1
    previous_index = _previous_nonblank_index(lines, next_h1)
    if previous_index is not None and _looks_like_breadcrumb(lines[previous_index]):
        keep_from = previous_index
    return "\n".join(lines[:first_h1] + lines[keep_from:])


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
