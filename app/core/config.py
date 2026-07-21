"""Central application configuration.

All environment-driven values live here. Nothing else in the codebase should
call os.environ / os.getenv directly - read settings from here instead, so
there is one auditable place that decides what is enabled (e.g. whether a
live LLM or WhatsApp provider is on).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_env: str = "local"
    app_debug: bool = True
    app_name: str = "laundrykhalas-whatsapp-agent"
    api_prefix: str = "/api"
    # Narrow, explicit allow-list for the admin UI dev server - never "*".
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Database ---
    database_url: str = (
        "postgresql+asyncpg://laundrykhalas:changeme_local_only@postgres:5432/laundrykhalas"
    )

    # --- Redis / Celery ---
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # --- Security (MVP placeholder auth) ---
    admin_api_key: str = "changeme_local_admin_key"

    # --- LLM Gateway ---
    llm_default_provider: str = "mock"
    llm_enable_anthropic: bool = False
    llm_enable_openai: bool = False
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_max_tokens_per_call: int = 1024
    llm_max_tool_steps: int = 10

    # --- WhatsApp channel ---
    whatsapp_provider: str = "mock"
    meta_whatsapp_enabled: bool = False
    meta_whatsapp_access_token: str = ""
    meta_whatsapp_phone_number_id: str = ""
    meta_whatsapp_waba_id: str = ""
    meta_whatsapp_verify_token: str = ""

    # --- Cost ceilings ---
    cost_max_tool_steps_per_run: int = 10
    cost_max_tokens_per_message: int = 2000
    cost_max_tokens_per_conversation_per_day: int = 20000
    cost_max_spend_per_customer_per_day_usd: float = 5.00
    cost_max_global_spend_per_day_usd: float = 200.00

    @property
    def live_llm_allowed(self) -> bool:
        """True only if a non-mock provider is both selected and explicitly enabled."""
        if self.llm_default_provider == "anthropic":
            return self.llm_enable_anthropic
        if self.llm_default_provider == "openai":
            return self.llm_enable_openai
        return False

    @property
    def live_whatsapp_allowed(self) -> bool:
        return self.whatsapp_provider != "mock" and self.meta_whatsapp_enabled

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
