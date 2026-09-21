from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    model: str
    num_ctx: int
    db_path: Path
    user_id: str
    user_role: str
    device_id: str
    max_iterations: int = 6
    request_timeout_s: float = 120.0
    schema_retries: int = 2
    empty_reply_retries: int = 1
    max_history_user_turns: int = 12
    temperature: float = 0.0
    voice_enabled: bool = False
    stt_model: str = "tiny"
    stt_device: str = "cpu"
    tts_provider: str = "edge"  # edge | sapi
    tts_voice: str = "en-GB-RyanNeural"


def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    db = Path(os.getenv("ARGUS_DB_PATH", "data/argus.db"))
    if not db.is_absolute():
        db = root / db
    return Settings(
        llm_base_url=os.getenv("ARGUS_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
        llm_api_key=os.getenv("ARGUS_LLM_API_KEY", "ollama"),
        model=os.getenv("ARGUS_MODEL", "qwen3:4b"),
        num_ctx=int(os.getenv("ARGUS_NUM_CTX", "4096")),
        db_path=db,
        user_id=os.getenv("ARGUS_USER_ID", "owner"),
        user_role=os.getenv("ARGUS_USER_ROLE", "owner"),
        device_id=os.getenv("ARGUS_DEVICE_ID", "laptop_01"),
        voice_enabled=os.getenv("ARGUS_VOICE_ENABLED", "0").lower()
        in {"1", "true", "yes", "on"},
        stt_model=os.getenv("ARGUS_STT_MODEL", "tiny"),
        stt_device=os.getenv("ARGUS_STT_DEVICE", "cpu"),
        tts_provider=os.getenv("ARGUS_TTS_PROVIDER", "edge").lower(),
        tts_voice=os.getenv("ARGUS_TTS_VOICE", "en-GB-RyanNeural"),
    )
