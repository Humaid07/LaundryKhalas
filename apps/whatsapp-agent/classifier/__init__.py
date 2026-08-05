"""WhatsApp intent classifier — internal routing component.

The classifier is an INTERNAL routing aid only. It never sends a message to a
customer, never calculates a price/discount/pickup-slot, and never performs a
route itself — it *recommends* a route and the backend router validates before
acting (CLAUDE.md §5/§6). In Stage 1 it runs in SHADOW MODE: it classifies,
persists, and logs, but does not change production routing.

Model separation (spec 2026-08-05):
  * main customer-facing agent → ANTHROPIC_WHATSAPP_MODEL (unchanged here)
  * classifier                 → ANTHROPIC_CLASSIFIER_MODEL (independent)

Public entry points:
  * classify_turn(...)      → run the full classification for one logical turn
  * preclassify(...)        → deterministic pre-LLM terminal decisions
  * select_route(...)       → recommend-only router (never sends)
"""
from classifier.schema import Classification, ClassifierStatus
from classifier.service import classify_turn
from classifier.deterministic import DeterministicResult, preclassify
from classifier.router import RouteDecision, select_route

__all__ = [
    "Classification",
    "ClassifierStatus",
    "classify_turn",
    "DeterministicResult",
    "preclassify",
    "RouteDecision",
    "select_route",
]
