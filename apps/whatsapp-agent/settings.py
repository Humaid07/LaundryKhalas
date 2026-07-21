"""Environment-driven settings for the standalone WhatsApp Agent.

Everything that gates a live call (LLM or WhatsApp) is read here and
nowhere else, so there is exactly one place that decides "mock vs live."
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# WhatsApp providers FastAPI can use. The dashboard never chooses a provider —
# it talks to FastAPI only; FastAPI decides based on WHATSAPP_MODE.
WHATSAPP_MODES = ("mock", "evolution", "meta")

# Required env vars per mode. mock needs nothing; each live provider requires
# ONLY its own vars — a blank var for the other provider never causes a failure.
_WHATSAPP_REQUIRED: dict[str, list[str]] = {
    "mock": [],
    "evolution": [
        "evolution_api_base_url",
        "evolution_api_key",
        "evolution_instance_name",
    ],
    "meta": [
        "meta_whatsapp_access_token",
        "meta_whatsapp_phone_number_id",
        "meta_whatsapp_business_account_id",
        "meta_whatsapp_verify_token",
        "meta_whatsapp_app_secret",
    ],
}


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

    # WhatsApp provider: mock (default) | evolution (current) | meta (future).
    whatsapp_mode: str = "mock"

    # Evolution API — CURRENT provider for WhatsApp testing. Required only when
    # whatsapp_mode=evolution.
    evolution_api_base_url: str = ""
    evolution_api_key: str = ""
    evolution_instance_name: str = ""

    # Meta WhatsApp Cloud API — FUTURE provider. Placeholders; required only when
    # whatsapp_mode=meta. Never required for mock or evolution.
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
    def _whatsapp_required_fields(self) -> list[str]:
        return _WHATSAPP_REQUIRED.get(self.whatsapp_mode.lower(), [])

    @property
    def missing_whatsapp_config(self) -> list[str]:
        """Required env vars (UPPERCASE) for the ACTIVE mode that are blank.
        Never includes another provider's vars — so blank Meta keys don't count
        in evolution/mock mode, and vice versa."""
        return [f.upper() for f in self._whatsapp_required_fields if not getattr(self, f, "")]

    @property
    def live_whatsapp_ready(self) -> bool:
        """True only when a real provider (evolution|meta) is selected AND all of
        its required config is present. Mock is never 'live'."""
        if self.whatsapp_mode.lower() not in ("evolution", "meta"):
            return False
        return not self.missing_whatsapp_config

    @property
    def meta_live_ready(self) -> bool:
        """True only in meta mode with all Meta config present. Used by the Meta
        Cloud API webhook to decide whether to actually send a live reply."""
        return self.whatsapp_mode.lower() == "meta" and not self.missing_whatsapp_config

    def validate_whatsapp_config(self) -> None:
        """Raise if the ACTIVE mode is unknown or missing its required vars.

        mock requires nothing (never raises). evolution/meta require ONLY their
        own vars — blank vars for the other provider never cause startup to fail.
        """
        mode = self.whatsapp_mode.lower()
        if mode not in WHATSAPP_MODES:
            raise ValueError(
                f"WHATSAPP_MODE must be one of {'|'.join(WHATSAPP_MODES)} (got '{self.whatsapp_mode}')."
            )
        missing = self.missing_whatsapp_config
        if missing:
            raise ValueError(
                f"WHATSAPP_MODE={mode} requires these env vars to be set: "
                f"{', '.join(missing)}. (Do not commit real keys.)"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
