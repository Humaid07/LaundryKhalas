"""Replay harness configuration — read from environment with safe defaults.

Kept separate from the app's `settings.py` so the harness is self-contained and
its safety-critical flags are explicit. Booleans DEFAULT TO SAFE (real sends /
payments / notifications off, capture-only on, PII redaction on).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Default search locations for the archives when the configured path is absent.
_DEFAULT_SEARCH_DIRS = [
    "./test-data/whatsapp",
    "../../test-data/whatsapp",
    str(Path.home() / "Downloads"),
    "./test-data",
]

TIMING_MODES = ("ACCELERATED_TIMING", "ORIGINAL_TIMING")
DATE_MODES = ("HISTORICAL_DATE_CONTEXT", "CURRENT_DATE_CONTEXT")
MEMORY_MODES = ("CUSTOMER_HISTORY", "ISOLATED_CHAT")


@dataclass
class ReplayConfig:
    # ---- sources -----------------------------------------------------------
    primary_source_path: str = "./test-data/whatsapp/WhatsApp_All_Chats.zip"
    fallback_source_path: str = "./test-data/whatsapp/chats_html.zip"

    # ---- safety (default safe) --------------------------------------------
    replay_mode: bool = True
    capture_only: bool = True
    allow_real_sends: bool = False
    allow_real_payments: bool = False
    allow_real_notifications: bool = False
    allow_real_facility_dispatch: bool = False
    allow_real_driver_dispatch: bool = False
    allow_production_db_writes: bool = False

    # ---- privacy -----------------------------------------------------------
    redact_pii: bool = True

    # ---- timing / dates / memory ------------------------------------------
    timing_mode: str = "ACCELERATED_TIMING"
    time_scale: float = 0.02
    max_delay_seconds: float = 3.0
    date_mode: str = "HISTORICAL_DATE_CONTEXT"
    # ISOLATED_CHAT (default): replay each chat independently so a takeover in one
    # chat never holds another. CUSTOMER_HISTORY shares one identity per customer
    # to test returning-customer memory (see isolation.assign_identities caveat).
    customer_memory_mode: str = "ISOLATED_CHAT"

    # ---- concurrency / rate / cost ----------------------------------------
    max_concurrency: int = 5
    requests_per_minute: int = 40
    max_retries: int = 3
    max_cost_usd: float = 70.0
    allow_exceed_cost_ceiling: bool = False

    # ---- model override ----------------------------------------------------
    model: str = "claude-sonnet-5"

    # ---- output ------------------------------------------------------------
    results_root: str = "./replay-results"

    # populated by resolve_sources()
    resolved_primary_path: Optional[str] = field(default=None, repr=False)
    resolved_fallback_path: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "ReplayConfig":
        return cls(
            primary_source_path=os.getenv(
                "WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH",
                cls.primary_source_path,
            ),
            fallback_source_path=os.getenv(
                "WHATSAPP_REPLAY_FALLBACK_SOURCE_PATH",
                cls.fallback_source_path,
            ),
            replay_mode=_bool("WHATSAPP_REPLAY_MODE", True),
            capture_only=_bool("WHATSAPP_REPLAY_CAPTURE_ONLY", True),
            allow_real_sends=_bool("WHATSAPP_REPLAY_ALLOW_REAL_SENDS", False),
            allow_real_payments=_bool("WHATSAPP_REPLAY_ALLOW_REAL_PAYMENTS", False),
            allow_real_notifications=_bool(
                "WHATSAPP_REPLAY_ALLOW_REAL_NOTIFICATIONS", False
            ),
            allow_real_facility_dispatch=_bool(
                "WHATSAPP_REPLAY_ALLOW_REAL_FACILITY_DISPATCH", False
            ),
            allow_real_driver_dispatch=_bool(
                "WHATSAPP_REPLAY_ALLOW_REAL_DRIVER_DISPATCH", False
            ),
            allow_production_db_writes=_bool(
                "WHATSAPP_REPLAY_ALLOW_PRODUCTION_DB_WRITES", False
            ),
            redact_pii=_bool("WHATSAPP_REPLAY_REDACT_PII", True),
            timing_mode=os.getenv(
                "WHATSAPP_REPLAY_TIMING_MODE", "ACCELERATED_TIMING"
            ),
            time_scale=_float("WHATSAPP_REPLAY_TIME_SCALE", 0.02),
            max_delay_seconds=_float("WHATSAPP_REPLAY_MAX_DELAY_SECONDS", 3.0),
            date_mode=os.getenv(
                "WHATSAPP_REPLAY_DATE_MODE", "HISTORICAL_DATE_CONTEXT"
            ),
            customer_memory_mode=os.getenv(
                "WHATSAPP_REPLAY_CUSTOMER_MEMORY_MODE", "ISOLATED_CHAT"
            ),
            max_concurrency=_int("WHATSAPP_REPLAY_MAX_CONCURRENCY", 5),
            requests_per_minute=_int("WHATSAPP_REPLAY_REQUESTS_PER_MINUTE", 40),
            max_retries=_int("WHATSAPP_REPLAY_MAX_RETRIES", 3),
            max_cost_usd=_float("WHATSAPP_REPLAY_MAX_COST_USD", 70.0),
            allow_exceed_cost_ceiling=_bool(
                "WHATSAPP_REPLAY_ALLOW_EXCEED_COST", False
            ),
            model=os.getenv("WHATSAPP_REPLAY_MODEL", "claude-sonnet-5"),
            results_root=os.getenv("WHATSAPP_REPLAY_RESULTS_ROOT", "./replay-results"),
        )

    # ---- source resolution -------------------------------------------------
    def resolve_sources(self, extra_search_dirs: Optional[list[str]] = None) -> None:
        """Resolve archive paths; search fallback dirs if configured path absent."""
        self.resolved_primary_path = _find_archive(
            self.primary_source_path,
            ["WhatsApp_All_Chats.zip"],
            extra_search_dirs,
        )
        self.resolved_fallback_path = _find_archive(
            self.fallback_source_path,
            ["chats_html.zip"],
            extra_search_dirs,
        )

    def validate_enums(self) -> list[str]:
        problems: list[str] = []
        if self.timing_mode not in TIMING_MODES:
            problems.append(f"WHATSAPP_REPLAY_TIMING_MODE must be one of {TIMING_MODES}")
        if self.date_mode not in DATE_MODES:
            problems.append(f"WHATSAPP_REPLAY_DATE_MODE must be one of {DATE_MODES}")
        if self.customer_memory_mode not in MEMORY_MODES:
            problems.append(
                f"WHATSAPP_REPLAY_CUSTOMER_MEMORY_MODE must be one of {MEMORY_MODES}"
            )
        return problems


def _find_archive(
    configured: str,
    basenames: list[str],
    extra_search_dirs: Optional[list[str]] = None,
) -> Optional[str]:
    """Return an existing path for the archive, or None.

    Search order: configured path, then <search dir>/<basename> for each default
    (and extra) directory. Never fails here — the caller decides whether a
    missing archive is fatal.
    """
    p = Path(configured).expanduser()
    if p.is_file():
        return str(p.resolve())

    dirs = list(_DEFAULT_SEARCH_DIRS)
    if extra_search_dirs:
        dirs = extra_search_dirs + dirs
    for d in dirs:
        for base in basenames:
            cand = Path(d).expanduser() / base
            if cand.is_file():
                return str(cand.resolve())
    return None
