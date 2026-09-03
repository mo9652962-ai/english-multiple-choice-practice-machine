"""Normalize option rows that contain multiple labelled choices.

Some Word/OCR exports put a second choice in the same text cell, for example
``"first choice\tB. second choice"``. The database and the ESQ format both
expect one option per row, so this module is shared by both import paths and
the repair script.
"""

from __future__ import annotations

import re
from typing import Any


EMBEDDED_OPTION_MARK_RE = re.compile(
    r"(?:^|[\t\r\n])\s*([A-Da-d])\s*(?:[.]|[．]|[、]|[)])\s*"
)


def split_embedded_option_content(key: str, content: str) -> list[tuple[str, str]]:
    """Return labelled pieces when *content* embeds another A-D option.

    The first piece keeps the row's key when the source omitted its leading
    label. A leading label is removed from the content. Plain multiline
    option text and tabs that are not followed by an option label are left
    untouched.
    """

    text = str(content or "").strip()
    source_key = str(key or "").strip().upper()
    matches = list(EMBEDDED_OPTION_MARK_RE.finditer(text))
    if not matches:
        return [(source_key, text)]

    pieces: list[tuple[str, str]] = []
    first = matches[0]
    if first.start() > 0:
        prefix = text[: first.start()].strip()
        if prefix:
            pieces.append((source_key, prefix))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        piece = text[match.end() : end].strip()
        if piece:
            pieces.append((match.group(1).upper(), piece))

    # A single leading marker is not a multi-option split. Keep it verbatim so
    # a legitimate option whose content starts with ``A.`` is not changed.
    if len(pieces) == 1 and first.start() == 0:
        return [(source_key, text)]
    return pieces or [(source_key, text)]


def normalize_option_rows(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand embedded options while preserving all other option metadata."""

    normalized: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            normalized.append(option)
            continue
        pieces = split_embedded_option_content(
            str(option.get("key", "")),
            str(option.get("content", "")),
        )
        for piece_key, piece_content in pieces:
            item = dict(option)
            item["key"] = piece_key
            item["content"] = piece_content
            normalized.append(item)
    return normalized
