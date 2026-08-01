"""Deterministic "how does it work" process explanation (spec 2026-08-01 §5).

Detects when a customer is asking how the Laundry Khalaas service works and
returns the approved concise four-step guide. Numbered steps are used ONLY here
(the one scenario where a structured list improves clarity); the wording says
"one of the nearest suitable facilities" because facility selection depends on
more than distance and must be validated by the backend. Pure and offline.
"""
from __future__ import annotations

import re

# Intent detection — questions equivalent to "how does it work / what is your
# process / how do I order / what happens after I book".
_PROCESS_PATTERNS = [
    r"how (?:does|do) (?:it|this|that|you|your service|the service|laundry\s*khala+s) (?:work|works|operate)",
    r"how (?:do i|can i|to) (?:place|make|book|put|start|get) (?:an? |my )?(?:order|laundry|pickup|booking)",
    r"how (?:does|do) (?:it|the) (?:process|procedure|booking) work",
    r"what(?:'?s| is| are)? (?:your|the) (?:process|procedure|steps)",
    r"what process (?:do|does)",
    r"what happens (?:after|when|once) i (?:book|order|place)",
    r"how (?:will|do) (?:my|you|the) .*(?:collect|collected|pick(?:ed)?|deliver|delivered)",
    r"how can i get my laundry (?:done|cleaned|washed)",
    r"how do you (?:all |guys )?work",
    r"laundry\s*khala+s process",
]
_PROCESS_RE = re.compile("|".join(_PROCESS_PATTERNS), re.IGNORECASE)

# The approved response (numbered steps allowed here only; no dash bullets).
PROCESS_EXPLANATION = (
    "Here is how it works:\n"
    "1. You book on WhatsApp and share your name, contact number, address, "
    "location pin and required service.\n"
    "2. Our driver collects your order and takes it to one of the nearest suitable "
    "facilities for processing.\n"
    "3. Once processed, we send you a Stripe payment link on WhatsApp.\n"
    "4. Once completed, we dispatch it for delivery."
)


def is_process_question(text: str | None) -> bool:
    """True when the message asks how the Laundry Khalaas service works."""
    if not text or not str(text).strip():
        return False
    return bool(_PROCESS_RE.search(str(text)))


def process_explanation() -> str:
    """The approved concise four-step process guide."""
    return PROCESS_EXPLANATION
