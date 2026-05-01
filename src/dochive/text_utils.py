from __future__ import annotations


MOJIBAKE_MARKERS = ("\u00d0", "\u00d1", "\u00c2", "\u00e2")


def repair_mojibake(text: str | None) -> str:
    if not text:
        return ""
    marker_count = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    if marker_count < 2:
        return text
    raw = bytearray()
    try:
        for char in text:
            codepoint = ord(char)
            if codepoint <= 255:
                raw.append(codepoint)
            else:
                raw.extend(char.encode("cp1252", errors="strict"))
        repaired = bytes(raw).decode("utf-8", errors="strict")
    except UnicodeError:
        return text
    if sum(repaired.count(marker) for marker in MOJIBAKE_MARKERS) < marker_count:
        return repaired
    return text
