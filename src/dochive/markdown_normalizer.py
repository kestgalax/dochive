from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from .text_utils import repair_mojibake

_COPY_CODE_CONTROL_RE = re.compile(r"^(?:\[(?:copy|copy code)\]\([^)]+\)|(?:copy|copy code))$", re.IGNORECASE)
_FENCED_CODE_RE = re.compile(r"^\s*(```|~~~)")
_RAW_HTML_EXAMPLE_RE = re.compile(
    r"^</?(?:a|br|h[1-6]|strong|em|p|div|span)\b[^>]*>(?:[^<]*</(?:a|h[1-6]|strong|em|p|div|span)>)?$",
    re.IGNORECASE,
)
_NEXT_LINK_RE = re.compile(r"^\s*(?:\\?\*\\?\*)?\s*Далее\s*>>", re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
_MARKDOWN_HEADING_PARSE_RE = re.compile(r"^(\s{0,3}#{1,6}\s+)(.*\S)\s*$")
_MARKDOWN_LINK_TOKEN_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_EMPTY_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[(?:\s*)\]\([^)]+\)")
_INLINE_PERMALINK_SYMBOL_RE = re.compile(r"^\s*(?:¶|#|🔗|🔖|link)\s+", re.IGNORECASE)
_LEADING_MARKDOWN_LINK_RE = re.compile(r"^\s*\[([^\]]*)\]\((.*)\)\s+(.+)$")


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


def normalize_markdown(
    markdown: str,
    *,
    clean: bool = True,
    extra_noise_lines: tuple[str, ...] = (),
    anchor_headings: dict[str, str] | None = None,
) -> str:
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
        text = _normalize_heading_permalinks(text)
        text = _drop_leading_heading_anchor_links(text, anchor_headings or {})
        text = _drop_footer_chrome(text)
        text = _collapse_repeated_lines(text)
        text = _normalize_blank_lines(text)
    text = _fix_empty_markdown_links(text)
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


def _fix_empty_markdown_links(text: str) -> str:
    output: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence:
            cleaned = _EMPTY_MARKDOWN_LINK_RE.sub("", line)
            if cleaned != line:
                cleaned = re.sub(r" {2,}", " ", cleaned)
                line = cleaned
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


def _drop_leading_heading_anchor_links(text: str, anchor_headings: dict[str, str]) -> str:
    if not anchor_headings:
        return text

    known_targets = {
        _normalize_anchor_target(target)
        for target in (*anchor_headings.keys(), *anchor_headings.values())
        if _normalize_anchor_target(target)
    }
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    dropped = False
    while index < len(lines):
        line = lines[index]
        if not line.strip() or _MARKDOWN_HEADING_RE.match(line.strip()) or _looks_like_breadcrumb(line):
            output.append(line)
            index += 1
            continue
        if _is_heading_anchor_link_line(line, known_targets):
            dropped = True
            index += 1
            continue
        break

    if dropped and not any(line.strip() for line in lines[index:]):
        return text
    output.extend(lines[index:])
    return "\n".join(output)


def _normalize_heading_permalinks(text: str) -> str:
    output: list[str] = []
    previous_heading_key = ""
    for line in text.splitlines():
        normalized = _normalize_heading_permalink(line)
        heading_key = _heading_dedupe_key(normalized)
        if heading_key and heading_key == previous_heading_key:
            continue
        output.append(normalized)
        if heading_key:
            previous_heading_key = heading_key
        elif normalized.strip():
            previous_heading_key = ""
    return "\n".join(output)


def _normalize_heading_permalink(line: str) -> str:
    match = _MARKDOWN_HEADING_PARSE_RE.match(line)
    if not match:
        return line
    prefix, heading = match.groups()
    prefix = prefix.strip() + " "
    cleaned = heading.strip()
    while True:
        candidate = _drop_leading_permalink(cleaned)
        if candidate == cleaned:
            break
        cleaned = candidate
    cleaned = _unwrap_heading_emphasis(cleaned)
    return prefix + cleaned


def _drop_leading_permalink(text: str) -> str:
    match = _LEADING_MARKDOWN_LINK_RE.match(text)
    if match:
        label, target, rest = match.groups()
        if _is_permalink_label(label) and "#" in target:
            return rest.strip()
    return _INLINE_PERMALINK_SYMBOL_RE.sub("", text, count=1).strip()


def _is_permalink_label(label: str) -> bool:
    normalized = re.sub(r"\s+", " ", label).strip().casefold()
    return normalized in {"", "¶", "#", "link", "🔗", "🔖"}


def _unwrap_heading_emphasis(text: str) -> str:
    stripped = text.strip()
    for marker in ("**", "__"):
        if stripped.startswith(marker) and stripped.endswith(marker) and len(stripped) > len(marker) * 2:
            return stripped[len(marker) : -len(marker)].strip()
    return stripped


def _heading_dedupe_key(line: str) -> str:
    match = _MARKDOWN_HEADING_PARSE_RE.match(line)
    if not match:
        return ""
    text = re.sub(r"\s+", " ", match.group(2)).strip().casefold()
    return f"{len(match.group(1).strip())}:{text}"


def _is_heading_anchor_link_line(line: str, known_targets: set[str]) -> bool:
    stripped = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line.strip())
    if not stripped:
        return False

    position = 0
    found = False
    while position < len(stripped):
        while position < len(stripped) and stripped[position].isspace():
            position += 1
        match = _MARKDOWN_LINK_TOKEN_RE.match(stripped, position)
        if not match:
            return False
        target = _normalize_anchor_target(_target_fragment(match.group(2)))
        label = _normalize_anchor_target(match.group(1))
        if target not in known_targets and label not in known_targets:
            return False
        found = True
        position = match.end()
    return found


def _target_fragment(target: str) -> str:
    target = target.strip()
    if target.startswith("#"):
        return unquote(target[1:]).strip()
    return unquote(urlparse(target).fragment).strip()


def _normalize_anchor_target(target: str) -> str:
    return re.sub(r"\s+", " ", target).strip()


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
    if heading_index is None:
        heading_index = _first_heading_index(lines)
    if heading_index is None or heading_index == 0:
        return text

    keep_from = heading_index
    previous_index = _previous_nonblank_index(lines, heading_index)
    if previous_index is not None:
        if _looks_like_breadcrumb(lines[previous_index]) or _looks_like_plain_article_title(lines[previous_index]):
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


def _first_heading_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _MARKDOWN_HEADING_RE.match(line.strip()):
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


def _looks_like_plain_article_title(line: str) -> bool:
    normalized = _line_text(line)
    if not normalized or "](" in normalized or normalized.startswith(("* ", "- ")):
        return False
    if len(normalized) > 140:
        return False
    lowered = normalized.casefold()
    chrome_words = {
        "поиск",
        "search",
        "продажи",
        "sales",
        "прочее",
        "other",
        "регламенты и методики",
        "технические вопросы",
        "поддержка клиентов",
        "функциональные возможности",
    }
    return lowered not in chrome_words


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
    tail_start = max(0, len(lines) - 12)
    for index in range(tail_start, len(lines)):
        line = lines[index]
        normalized = _line_text(line)
        if _looks_like_footer_notice(normalized):
            start = _footer_start_index(lines, index)
            return "\n".join(lines[:start])
    return text


def _footer_start_index(lines: list[str], index: int) -> int:
    for candidate in range(index - 1, max(index - 4, -1), -1):
        normalized = _line_text(lines[candidate])
        if _looks_like_footer_heading_or_link(normalized):
            return candidate
    return index


def _looks_like_footer_notice(line: str) -> bool:
    lowered = line.lower()
    powered_by = "powered by" in lowered or "работает на" in lowered
    if powered_by and ("](" in line or "|" in line or lowered.strip().startswith(("powered by", "работает на"))):
        return True
    return any(
        marker in lowered
        for marker in (
            "legal notice",
            "public offer",
            "terms of use",
            "all rights reserved",
            "copyright",
            "ctrl+enter",
            "обращаем ваше внимание",
            "публичной оферт",
            "все права защищены",
            "сообщить об ошибке",
        )
    ) or bool(re.search(r"(?:©|&copy;|\bcopyright\b|\b20\d{2}\b).{0,80}(?:rights reserved|powered by|права защищены)", lowered))


def _looks_like_footer_heading_or_link(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "product page",
            "documentation home",
            "support",
            "feedback",
            "legal",
            "terms",
            "privacy",
            "cookies",
            "powered by",
            "страница продукта",
            "главная документации",
            "техническая поддержка",
            "обратная связь",
            "конфиденциальность",
            "правовая информация",
        )
    )


def _line_text(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\s*[-*]\s+", "* ", line)
    line = re.sub(r"\s+", " ", line)
    return line
