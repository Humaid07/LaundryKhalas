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

    # Demo (is_demo=true) rows are seeded fake orders/customers for local dev &
    # demos. When false (the production-safe default), dashboard order APIs
    # EXCLUDE is_demo rows and the local SQLite auto-seed is skipped. Real
    # WhatsApp orders are is_demo=false, so they always show regardless.
    enable_demo_data: bool = False

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
    # When true, the agent's happy-path draft reply is auto-sent via Evolution on
    # inbound. Default false = replies are held for human approval (MVP rule);
    # escalations are always held regardless.
    #
    # SAFETY: auto-reply is ALSO gated by evolution_allowed_test_numbers below.
    # EVOLUTION_AUTO_REPLY=true now means "auto-reply ONLY for allowed test
    # numbers AND only when the message is safe and laundry-related" — never a
    # blanket reply to every WhatsApp number.
    evolution_auto_reply: bool = False

    # Comma-separated E.164 allow-list of senders the agent may auto-reply to
    # while testing. Empty = no one is auto-replied to (fail safe). Any inbound
    # from a number not on this list is stored/logged but never gets an
    # autonomous reply. Example: EVOLUTION_ALLOWED_TEST_NUMBERS=+971502485658
    evolution_allowed_test_numbers: str = ""

    # Native WhatsApp interactive LIST messages via Evolution (/message/sendList).
    # Verified working on Evolution 2.3.7 + Baileys once every row carries a
    # non-empty description (empty rows 400 with "description cannot be empty").
    # Default true → service/slot/instruction selection is sent as a real
    # tappable list; on ANY send failure it still falls back to numbered text.
    evolution_use_interactive: bool = True

    # Native WhatsApp reply BUTTONS via Evolution (/message/sendButtons). The
    # payload is accepted, but button RENDERING on Baileys is inconsistent across
    # WhatsApp client versions, and a 200-but-not-rendered send cannot trigger the
    # fallback. Default false → button prompts (date / confirm / next-actions) are
    # sent as numbered text, which is reliably answerable. Flip to true to trial
    # native buttons on a build/number where they render.
    evolution_use_buttons: bool = False

    # Agent operating mode: test | live | paused. SAFE DEFAULT = paused (the
    # agent NEVER auto-replies live by accident — a missing/invalid value also
    # resolves to paused).
    #   test   -> reply ONLY to numbers on EVOLUTION_ALLOWED_TEST_NUMBERS
    #   live   -> reply to every valid customer number
    #   paused -> store incoming messages, send NO automated reply
    whatsapp_agent_mode: str = "paused"

    # Draft orders with no confirmation older than this become 'abandoned' when the
    # expiry job runs (scripts/expire_drafts.py). Confirmed orders are never touched.
    draft_expiry_hours: int = 24

    # --- Auth / RBAC ---
    # When true, every dashboard /api/* endpoint requires a valid JWT + role.
    # Default false so local dev works without logging in; MUST be true in
    # staging/production. Webhooks and /health are never auth-gated.
    require_auth: bool = False
    # HMAC secret for signing dashboard JWTs. MUST be set (long random) when
    # require_auth=true. In dev an ephemeral fallback is used with a warning.
    jwt_secret: str = ""
    jwt_expiry_hours: int = 12

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
    def jwt_secret_effective(self) -> str:
        """The JWT signing secret. Falls back to a fixed dev-only secret when
        unset AND auth is not required; when require_auth=true a real JWT_SECRET
        must be provided (an unset secret makes tokens unverifiable → all
        requests are rejected, which is fail-safe)."""
        if self.jwt_secret:
            return self.jwt_secret
        return "" if self.require_auth else "dev-only-insecure-jwt-secret"

    @property
    def agent_operating_mode(self) -> str:
        """Normalized WhatsApp operating mode (test|live|paused); anything
        unrecognized resolves to the safe 'paused' (never accidentally 'live').
        Distinct from the unrelated ``agent_mode`` field ('standalone')."""
        m = (self.whatsapp_agent_mode or "").strip().lower()
        return m if m in ("test", "live", "paused") else "paused"

    @property
    def agent_replies_enabled(self) -> bool:
        """True in test/live, False in paused. Sending still additionally requires
        evolution_live_ready and (in test) the sender allow-list."""
        return self.agent_operating_mode in ("test", "live")

    @property
    def allowed_auto_reply_numbers(self) -> frozenset[str]:
        """Normalized E.164 set of senders the agent may auto-reply to. Parsed
        from EVOLUTION_ALLOWED_TEST_NUMBERS (comma-separated). Normalization is
        the SAME function the webhook uses on the inbound sender, so comparison
        is format-independent (JID / whatsapp: / +country / bare digits)."""
        from services.privacy import normalize_e164

        return frozenset(
            n
            for n in (normalize_e164(p) for p in self.evolution_allowed_test_numbers.split(","))
            if n
        )

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

    @property
    def evolution_live_ready(self) -> bool:
        """True only in evolution mode with all Evolution config present. Gates
        live sends/receives via the Evolution API."""
        return self.whatsapp_mode.lower() == "evolution" and not self.missing_whatsapp_config

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
