from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "https://ollama.cloud")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    hotel_api_base_url: str = os.getenv("HOTEL_API_BASE_URL", "https://hotel-system.internal/api")
    hotel_api_key: str = os.getenv("HOTEL_API_KEY", "")
    state_ttl_seconds: int = int(os.getenv("STATE_TTL_SECONDS", "3600"))


settings = Settings()
