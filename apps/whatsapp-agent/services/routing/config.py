"""Routing mode + rollout policy (pure, deterministic).

Decides, per order, whether the ADVANCED engine runs at all and whether its
selection is AUTHORITATIVE (vs the legacy production router). Canary cohorting is
deterministic on the order id + routing version, so retries of the same order
never flip between legacy and advanced.
"""

from __future__ import annotations

import hashlib

ROUTING_VERSION = "ADVANCED_ROUTING_V1"

OFF = "off"
SHADOW = "shadow"
CANARY = "canary"
LIVE = "live"
SIMULATOR = "simulator"

_VALID_MODES = frozenset({OFF, SHADOW, CANARY, LIVE})


def resolve_mode(settings) -> str:
    """Effective mode: OFF unless the engine is enabled and the mode is valid."""
    if not getattr(settings, "advanced_routing_enabled", False):
        return OFF
    mode = (getattr(settings, "advanced_routing_mode", OFF) or OFF).strip().lower()
    return mode if mode in _VALID_MODES else OFF


def cohort_bucket(order_id: str, routing_version: str = ROUTING_VERSION) -> int:
    """Deterministic 0..99 bucket for an order (stable across retries)."""
    basis = f"{order_id}|{routing_version}".encode("utf-8")
    return int(hashlib.sha1(basis).hexdigest(), 16) % 100


def should_run_advanced(settings, *, is_test: bool) -> bool:
    """Whether to EVALUATE the advanced engine for this order.

    - Test orders: only when the engine is enabled AND test routing is allowed.
    - Production orders: whenever the engine is enabled and the mode is not off
      (shadow evaluates without being authoritative)."""
    if not getattr(settings, "advanced_routing_enabled", False):
        return False
    if is_test:
        return bool(getattr(settings, "allow_test_facility_routing", False))
    return resolve_mode(settings) != OFF


def advanced_is_authoritative(settings, *, is_test: bool, order_id: str,
                              routing_version: str = ROUTING_VERSION) -> bool:
    """Whether the advanced selection ASSIGNS the order (vs legacy assigning).

    - Test orders never use the legacy router: advanced is authoritative whenever
      it runs.
    - Production: authoritative in LIVE, or in CANARY when the order's deterministic
      cohort falls under the canary percentage. SHADOW never assigns."""
    if not should_run_advanced(settings, is_test=is_test):
        return False
    if is_test:
        return True
    mode = resolve_mode(settings)
    if mode == LIVE:
        return True
    if mode == CANARY:
        pct = max(0, min(100, int(getattr(settings, "advanced_routing_canary_percentage", 0) or 0)))
        return cohort_bucket(order_id, routing_version) < pct
    return False  # off / shadow


def fallback_enabled(settings) -> bool:
    return bool(getattr(settings, "advanced_routing_fallback_to_legacy", True))


def snapshot_required(settings) -> bool:
    return bool(getattr(settings, "advanced_routing_require_decision_snapshot", True))
