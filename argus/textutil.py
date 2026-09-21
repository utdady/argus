from __future__ import annotations

import re

# Broad emoji / pictograph ranges (chat + TTS should stay plain text).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # misc symbols & pictographs, emoticons, etc.
    "\U0001FA00-\U0001FAFF"  # extended-A
    "\U00002700-\U000027BF"  # dingbats
    "\U00002600-\U000026FF"  # misc symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0000200D"  # ZWJ
    "\U0000FE0F"  # variation selector
    "]+",
    flags=re.UNICODE,
)

_MULTISPACE_RE = re.compile(r"[ \t]{2,}")


def strip_emojis(text: str) -> str:
    """Remove emoji / pictographs; keep normal punctuation and letters."""
    if not text:
        return ""
    cleaned = _EMOJI_RE.sub("", text)
    cleaned = _MULTISPACE_RE.sub(" ", cleaned)
    return cleaned.strip()
