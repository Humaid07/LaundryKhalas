"""Environment-driven settings for the standalone WhatsApp Agent.

Everything that gates a live call (LLM or WhatsApp) is read here and
nowhere else, so there is exactly one place that decides "mock vs live."
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# WhatsApp providers FastAPI can use. The dashboard never chooses a provider —
# it talks to FastAPI only; FastAPI decides based on WHATSAPP_MODE.
WHATSAPP_MODES = ("mock", "evolution", "meta")

# Default Anthropic model when neither ANTHROPIC_MODEL nor LLM_MODEL is set. Kept
# in ONE place (not hardcoded across the codebase) and always overridable via
# env — do not scatter model ids through the code.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"

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
    # Blank → each provider's own default (Anthropic: claude-opus-4-8). Set an
    # exact model id (no date suffix) to override, e.g. claude-haiku-4-5 to cut
    # cost on the high-volume WhatsApp path. Never invent a model id.
    llm_model: str = ""

    # --- AI provider (Anthropic) tunables -----------------------------------
    # AI_PROVIDER / ANTHROPIC_MODEL are the spec-facing names; they fall back to
    # the legacy LLM_PROVIDER / LLM_MODEL so existing .env files keep working
    # (see ai_provider / anthropic_model_effective below). The key lives ONLY in
    # ANTHROPIC_API_KEY and is never echoed in any status/validation output.
    ai_provider: str = ""            # falls back to llm_provider when blank
    anthropic_model: str = ""        # falls back to llm_model when blank
    anthropic_enabled: bool = True   # master kill-switch; false → never call Claude
    anthropic_tool_use_enabled: bool = True
    anthropic_log_usage: bool = True
    # When false (default, production-safe) raw prompts/replies are NOT persisted;
    # only safe operational metadata (model, tokens, latency, tool names) is.
    anthropic_store_raw_content: bool = False
    anthropic_max_tokens: int = 800
    anthropic_temperature: float = 0.2   # ignored for models that reject sampling params
    anthropic_timeout_seconds: int = 30
    anthropic_max_retries: int = 3       # APPLICATION-controlled retries (SDK retries are off)
    anthropic_max_tool_rounds: int = 5
    anthropic_history_message_limit: int = 20
    anthropic_history_character_limit: int = 20000
    # Let Claude ORCHESTRATE the booking via controlled write-tools (save_*/
    # confirm_order) instead of the deterministic FSM. SAFE DEFAULT = false: the
    # proven deterministic booking flow stays the live path unless explicitly
    # enabled AND a live Claude provider is configured. The backend still
    # validates + persists every write either way.
    anthropic_booking_orchestration: bool = False

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
    # Default FALSE: current Evolution 2.3.7 + Baileys builds fail to ENCODE a
    # listMessage against the shipping WhatsApp Web protocol version — the send
    # 400s with "TypeError: this.isZero is not a function" (a library-level bug,
    # not a payload issue: no row/description tweak avoids it). With native lists
    # off, service/slot/instruction selection is sent directly as a reliably
    # answerable numbered-text menu (the same content the fallback produced),
    # skipping a doomed ~5s round-trip on every prompt. Set
    # EVOLUTION_USE_INTERACTIVE=true to re-trial native lists on a build/WhatsApp
    # Web version where sendList encodes successfully; on ANY send failure it
    # still falls back to numbered text.
    evolution_use_interactive: bool = False

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

    # --- AI provider resolution (spec names → legacy fallback) --------------
    @property
    def ai_provider_effective(self) -> str:
        """The active provider: AI_PROVIDER if set, else legacy LLM_PROVIDER."""
        return (self.ai_provider or self.llm_provider or "mock").strip().lower()

    @property
    def anthropic_model_effective(self) -> str:
        """Resolved Anthropic model id: ANTHROPIC_MODEL → LLM_MODEL → default.
        Never empty, so the provider always has a valid id (no hardcoding at the
        call site)."""
        return (self.anthropic_model or self.llm_model or DEFAULT_ANTHROPIC_MODEL).strip()

    @property
    def live_llm_ready(self) -> bool:
        """True only if a real provider is selected AND usable. For Anthropic that
        means AI_PROVIDER/LLM_PROVIDER=anthropic, ANTHROPIC_ENABLED=true, and a
        key present. OpenAI keeps its own gate. Nothing goes live otherwise."""
        provider = self.ai_provider_effective
        if provider == "anthropic":
            return self.anthropic_enabled and bool(self.anthropic_api_key)
        if provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def ai_status(self) -> dict:
        """Safe (secret-free) snapshot of the AI integration for health/status
        endpoints. NEVER includes the API key — only whether one is configured."""
        provider = self.ai_provider_effective
        return {
            "provider": provider,
            "enabled": self.anthropic_enabled if provider == "anthropic" else False,
            "configured": bool(self.anthropic_api_key) if provider == "anthropic" else False,
            "model_configured": bool(self.anthropic_model_effective) if provider == "anthropic" else False,
            "model": self.anthropic_model_effective if provider == "anthropic" else None,
            "tool_use_enabled": self.anthropic_tool_use_enabled,
            "live_ready": self.live_llm_ready,
        }

    def validate_ai_config(self) -> None:
        """Fail fast at startup on a misconfigured Anthropic integration, WITHOUT
        ever revealing the key. Only validates when Anthropic is the active,
        enabled provider — mock/openai never raise here."""
        if self.ai_provider_effective != "anthropic" or not self.anthropic_enabled:
            return
        if not self.anthropic_api_key:
            raise ValueError(
                "Anthropic is enabled (AI_PROVIDER=anthropic, ANTHROPIC_ENABLED=true) "
                "but ANTHROPIC_API_KEY is not set. Add it to the backend secret "
                "configuration (never to source control)."
            )
        if not self.anthropic_model_effective:
            raise ValueError("ANTHROPIC_MODEL (or LLM_MODEL) resolves to empty — set a valid model id.")
        checks = {
            "ANTHROPIC_MAX_TOKENS": (self.anthropic_max_tokens, 1, 200_000),
            "ANTHROPIC_TIMEOUT_SECONDS": (self.anthropic_timeout_seconds, 1, 600),
            "ANTHROPIC_MAX_RETRIES": (self.anthropic_max_retries, 0, 10),
            "ANTHROPIC_MAX_TOOL_ROUNDS": (self.anthropic_max_tool_rounds, 1, 20),
            "ANTHROPIC_HISTORY_MESSAGE_LIMIT": (self.anthropic_history_message_limit, 1, 500),
            "ANTHROPIC_HISTORY_CHARACTER_LIMIT": (self.anthropic_history_character_limit, 100, 500_000),
        }
        for name, (value, lo, hi) in checks.items():
            if not (isinstance(value, int) and lo <= value <= hi):
                raise ValueError(f"{name} must be an integer in [{lo}, {hi}] (got {value!r}).")
        if not (0.0 <= float(self.anthropic_temperature) <= 1.0):
            raise ValueError(
                f"ANTHROPIC_TEMPERATURE must be in [0.0, 1.0] (got {self.anthropic_temperature!r})."
            )

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
