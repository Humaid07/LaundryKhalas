"""Environment-driven settings for the standalone WhatsApp Agent.

Everything that gates a live call (LLM or WhatsApp) is read here and
nowhere else, so there is exactly one place that decides "mock vs live."
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_name: str = "LaundryKhalas WhatsApp Agent"
    agent_mode: str = "standalone"

    # --- Database mode / environment (dev/test Supabase project) ---
    # database_mode: "sqlite" (default local) | "supabase" (dev/test Postgres).
    # These gate the Supabase access layer and the seed/reset safety checks.
    database_env: str = "test"          # test | production
    database_mode: str = "sqlite"       # sqlite | supabase
    supabase_project_type: str = "test"  # test | production
    allow_test_seed: bool = False
    allow_test_reset: bool = False

    # Supabase connection. DATABASE_URL (below) is the backend-only Postgres DSN.
    # The service role key is BACKEND-ONLY and must never reach the frontend.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    llm_provider: str = "mock"  # mock | anthropic | openai
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = ""

    # Humanized typing indicator (frontend uses these to hold a "typing..."
    # bubble for a natural amount of time before showing the reply). The
    # backend only surfaces the values via /api/settings/status - it does
    # not itself sleep, so requests are never artificially blocked.
    agent_min_typing_delay_ms: int = 2000
    agent_max_typing_delay_ms: int = 3000

    whatsapp_mode: str = "mock"  # mock | live
    meta_whatsapp_access_token: str = ""
    meta_whatsapp_phone_number_id: str = ""
    meta_whatsapp_business_account_id: str = ""
    meta_whatsapp_verify_token: str = ""
    meta_whatsapp_app_secret: str = ""

    database_url: str = "sqlite+aiosqlite:///./whatsapp_agent.db"

    # :3100 = standalone chat UI · :3000 = internal admin dashboard (Operations tab)
    allowed_origins: str = (
        "http://localhost:3100,http://127.0.0.1:3100,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def live_llm_ready(self) -> bool:
        """True only if a real provider is selected AND its key is present."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def live_whatsapp_ready(self) -> bool:
        """True only if live mode is requested AND all required Meta config is present."""
        return self.whatsapp_mode == "live" and bool(
            self.meta_whatsapp_access_token
            and self.meta_whatsapp_phone_number_id
            and self.meta_whatsapp_verify_token
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
