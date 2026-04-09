from __future__ import annotations

import re


def strip_code_fence(text: str) -> str:
    value = text.strip()
    fence = re.match(r"^```(?:latex|tex|math|json)?\s*(.*?)\s*```$", value, re.S)
    if fence:
        return fence.group(1).strip()
    return value


def normalize_latex(text: str) -> str:
    value = strip_code_fence(text).strip()
    wrappers = [
        (r"^\$\$(.*)\$\$$", re.S),
        (r"^\$(.*)\$$", re.S),
        (r"^\\\[(.*)\\\]$", re.S),
        (r"^\\\((.*)\\\)$", re.S),
    ]
    for pattern, flags in wrappers:
        match = re.match(pattern, value, flags)
        if match:
            return match.group(1).strip()
    return value
