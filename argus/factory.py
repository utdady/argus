from __future__ import annotations

from argus.config import Settings, load_settings
from argus.orchestrator.loop import Orchestrator
from argus.permissions.policy import PermissionPolicy
from argus.providers.base import SpeechToText, TextToSpeech
from argus.providers.null_voice import NullSTT, NullTTS
from argus.providers.openai_compat import OpenAICompatProvider
from argus.storage.db import Storage
from argus.tools.builtin import build_builtin_registry


def build_orchestrator(settings: Settings | None = None) -> tuple[Orchestrator, Storage]:
    settings = settings or load_settings()
    store = Storage(settings.db_path)
    llm = OpenAICompatProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.model,
        num_ctx=settings.num_ctx,
        timeout_s=settings.request_timeout_s,
        default_temperature=settings.temperature,
    )
    orch = Orchestrator(
        settings=settings,
        llm=llm,
        registry=build_builtin_registry(),
        store=store,
        policy=PermissionPolicy(),
    )
    return orch, store


def build_voice(
    settings: Settings | None = None,
) -> tuple[SpeechToText, TextToSpeech, bool]:
    """Return (stt, tts, enabled). Falls back to null providers if voice deps missing."""
    settings = settings or load_settings()
    if not settings.voice_enabled:
        return NullSTT(), NullTTS(), False
    try:
        from argus.providers.sapi_tts import SapiTTS
        from argus.providers.whisper_stt import FasterWhisperSTT
    except Exception:
        return NullSTT(), NullTTS(), False
    try:
        stt = FasterWhisperSTT(
            model_size=settings.stt_model,
            device=settings.stt_device,
        )
        tts = SapiTTS()
        return stt, tts, True
    except Exception:
        return NullSTT(), NullTTS(), False
