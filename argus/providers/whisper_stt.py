from __future__ import annotations

import tempfile
from pathlib import Path


class FasterWhisperSTT:
    """Local STT via faster-whisper. Defaults to CPU so Ollama can keep the GPU."""

    def __init__(
        self,
        *,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Voice STT requires faster-whisper. Install with: pip install -e \".[voice]\""
            ) from exc
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def transcribe(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        if not audio:
            return ""
        mime = (mime_type or "").lower()
        if "wav" in mime or audio[:4] == b"RIFF":
            suffix = ".wav"
        elif "webm" in mime:
            # PyAV needs ffmpeg for many WebM streams; prefer client WAV.
            suffix = ".webm"
        else:
            suffix = ".wav"
        model = self._ensure_model()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio)
            path = Path(tmp.name)
        try:
            segments, _info = model.transcribe(str(path), beam_size=1)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text
        except Exception as exc:
            hint = ""
            if suffix == ".webm":
                hint = (
                    " WebM decode failed (ffmpeg often required). "
                    "Use WAV from the browser PTT button."
                )
            raise RuntimeError(f"STT decode failed: {exc}.{hint}") from exc
        finally:
            path.unlink(missing_ok=True)
