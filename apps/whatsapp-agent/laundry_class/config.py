"""Config for the Laundry Class LangGraph agent. Mock-first defaults: the live
LLM provider is only ever used when explicitly selected AND its key is present."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class LCConfig:
    llm_provider: str            # "mock" (default) | "anthropic"
    anthropic_api_key: str
    llm_model: str
    checkpoint_db: str           # path to the persistent LangGraph SQLite checkpointer

    @property
    def live_llm(self) -> bool:
        return self.llm_provider == "anthropic" and bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_config() -> LCConfig:
    return LCConfig(
        llm_provider=os.getenv("LC_LLM_PROVIDER", "mock").lower(),
        anthropic_api_key=os.getenv("LC_ANTHROPIC_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""),
        llm_model=os.getenv("LC_LLM_MODEL", ""),
        checkpoint_db=os.getenv("LC_CHECKPOINT_DB", str(_BASE / "laundry_class_memory.sqlite")),
    )
