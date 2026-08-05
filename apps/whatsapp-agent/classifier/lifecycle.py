"""Backend-controlled customer lifecycle.

The classifier is NEVER asked to invent whether a customer is new or existing
(spec). The backend resolves it from persisted facts and passes the resolved
stage INTO the classifier payload. This module is the single, pure mapping from
facts → lifecycle stage, so the rule is testable and consistent.

It intentionally does not read the DB — the caller gathers the facts (from
orders_repo / conversations_repo / crm_repo) and passes them in.
"""
from __future__ import annotations

from dataclasses import dataclass

from classifier import taxonomy as tax


@dataclass
class LifecycleFacts:
    has_completed_order: bool = False   # >=1 legitimate completed order
    has_active_order: bool = False      # an order currently in flight
    has_prior_conversation: bool = False  # previous enquiry / abandoned booking
    is_b2b_confirmed: bool = False      # backend-confirmed commercial account


def resolve_lifecycle(facts: LifecycleFacts) -> str:
    """Map persisted facts to one of taxonomy.LIFECYCLE_STAGES.

    Precedence (most specific first):
      B2B_LEAD          → backend has confirmed a commercial account
      ACTIVE_CUSTOMER   → an order is currently active
      EXISTING_CUSTOMER → at least one legitimate completed order
      RETURNING_PROSPECT→ prior conversation/enquiry but no completed order
      NEW_PROSPECT      → nothing known
    """
    if facts.is_b2b_confirmed:
        return "B2B_LEAD"
    if facts.has_active_order:
        return "ACTIVE_CUSTOMER"
    if facts.has_completed_order:
        return "EXISTING_CUSTOMER"
    if facts.has_prior_conversation:
        return "RETURNING_PROSPECT"
    return "NEW_PROSPECT"


def is_valid_stage(stage: str | None) -> bool:
    return stage in tax.LIFECYCLE_STAGES
