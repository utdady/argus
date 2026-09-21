from __future__ import annotations


class NullSTT:
    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        return ""


class NullTTS:
    def synthesize(self, text: str) -> tuple[bytes, str]:
        return b"", "audio/wav"
