from __future__ import annotations

import tempfile
from pathlib import Path


class SapiTTS:
    """Local TTS via pyttsx3 (Windows SAPI / platform engine). Returns WAV bytes."""

    def __init__(self, *, rate: int | None = None) -> None:
        self.rate = rate
        self._engine = None

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            import pyttsx3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Voice TTS requires pyttsx3. Install with: pip install -e \".[voice]\""
            ) from exc
        engine = pyttsx3.init()
        if self.rate is not None:
            engine.setProperty("rate", self.rate)
        self._engine = engine
        return engine

    def synthesize(self, text: str) -> tuple[bytes, str]:
        cleaned = (text or "").strip()
        if not cleaned:
            return b"", "audio/wav"
        engine = self._ensure_engine()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            engine.save_to_file(cleaned, str(path))
            engine.runAndWait()
            data = path.read_bytes()
            return data, "audio/wav"
        finally:
            path.unlink(missing_ok=True)
