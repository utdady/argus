from __future__ import annotations

import asyncio
import concurrent.futures
import tempfile
from collections.abc import Coroutine
from pathlib import Path
from typing import TypeVar

# Polished British male neural voices (Jarvis / butler-adjacent).
DEFAULT_BUTLER_VOICE = "en-GB-RyanNeural"

T = TypeVar("T")


def _run_async(coro: Coroutine[object, object, T]) -> T:
    """Run a coroutine from sync code, even inside FastAPI's event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already in an event loop — asyncio.run() is illegal here.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class EdgeTTS:
    """Neural TTS via Microsoft Edge voices (needs network). Returns MP3 bytes."""

    def __init__(self, *, voice: str = DEFAULT_BUTLER_VOICE, rate: str = "+0%") -> None:
        self.voice = voice
        self.rate = rate

    def synthesize(self, text: str) -> tuple[bytes, str]:
        cleaned = (text or "").strip()
        if not cleaned:
            return b"", "audio/mpeg"
        try:
            import edge_tts
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                'Voice neural TTS requires edge-tts. Install with: pip install -e ".[voice]"'
            ) from exc

        async def _run() -> bytes:
            communicate = edge_tts.Communicate(cleaned, self.voice, rate=self.rate)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                path = Path(tmp.name)
            try:
                await communicate.save(str(path))
                return path.read_bytes()
            finally:
                path.unlink(missing_ok=True)

        data = _run_async(_run())
        return data, "audio/mpeg"
