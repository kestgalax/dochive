from __future__ import annotations

import struct
from pathlib import Path


def read_image_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as file:
            header = file.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                width, height = struct.unpack(">II", header[16:24])
                return int(width), int(height)
            if header[:6] in {b"GIF87a", b"GIF89a"} and len(header) >= 10:
                width, height = struct.unpack("<HH", header[6:10])
                return int(width), int(height)
            if header.startswith(b"\xff\xd8"):
                return _read_jpeg_size(file)
    except OSError:
        return None
    return None


def _read_jpeg_size(file) -> tuple[int, int] | None:
    file.seek(2)
    while True:
        marker_start = file.read(1)
        if not marker_start:
            return None
        if marker_start != b"\xff":
            continue
        marker = file.read(1)
        while marker == b"\xff":
            marker = file.read(1)
        if marker in {
            b"\xc0",
            b"\xc1",
            b"\xc2",
            b"\xc3",
            b"\xc5",
            b"\xc6",
            b"\xc7",
            b"\xc9",
            b"\xca",
            b"\xcb",
            b"\xcd",
            b"\xce",
            b"\xcf",
        }:
            segment_length = file.read(2)
            if len(segment_length) != 2:
                return None
            data = file.read(5)
            if len(data) != 5:
                return None
            height, width = struct.unpack(">HH", data[1:5])
            return int(width), int(height)
        if marker in {b"\xd8", b"\xd9"}:
            continue
        segment_length = file.read(2)
        if len(segment_length) != 2:
            return None
        length = struct.unpack(">H", segment_length)[0]
        if length < 2:
            return None
        file.seek(length - 2, 1)
