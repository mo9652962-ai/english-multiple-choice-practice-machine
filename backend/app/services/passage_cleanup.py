from __future__ import annotations

import re


INLINE_BLANK_BREAK_RE = re.compile(
    r"(?P<before>\S)(?P<break>\n{2,})"
    r"(?=(?:\(\s*)?(?:[1-9]|[1-4]\d)(?:\s*\))?\s+_{2,})"
)


def repair_inline_blank_paragraph_breaks(passage: str) -> str:
    """Join false paragraph breaks immediately before numbered exam blanks."""

    def replace(match: re.Match[str]) -> str:
        before = match.group("before")
        if before in ".!?。！？)]}\"'”’":
            return match.group(0)
        return f"{before} "

    return INLINE_BLANK_BREAK_RE.sub(replace, passage)
