"""The real Section D.4 classification prompt.

Not used by the deterministic mock path in `tools.classify_text` (see that
module's docstring for why). This exists so that swapping in a live LLM
provider later is a prompt-and-parse change inside `agent.py`, not a
redesign - the same pattern `whatsapp_operations/prompts.py` documents for
its own templates.
"""


def render_classification_prompt(
    *,
    message_text: str,
    customer_name: str | None,
    country: str | None,
    current_sales_stage: str | None,
    recent_messages: list[str],
) -> str:
    recent = "\n".join(recent_messages[-3:]) if recent_messages else "(none)"
    return f"""You are a conversation classifier for LaundryKhalas. Given a message, classify it on three dimensions:

1. INTENT — one of:
   new_enquiry, quote_request, order_placement, order_tracking, complaint,
   pickup_issue, delivery_issue, payment_issue, facility_issue,
   pricing_objection, cancellation, rescheduling, b2b_lead,
   facility_onboarding, driver_support, lost_lead, repeat_order, general_enquiry

2. SENTIMENT — one of: happy, neutral, frustrated, urgent, angry
   Plus a numeric score from -1.0 (extremely angry) to +1.0 (extremely happy).

3. SALES_STAGE_DELTA — if this message changes the conversation's sales stage, indicate the new stage:
   new_lead, qualified, quoted, follow_up_needed, won, lost, or "no_change"

4. TOPIC — a 2-5 word topic label (e.g., "shirt damaged", "pricing too high", "late pickup")

Return ONLY valid JSON in this format:
{{
  "intent": "...",
  "sentiment": "...",
  "sentiment_score": ...,
  "sales_stage_delta": "...",
  "topic": "..."
}}

Context for the classification:
- Customer name: {customer_name or "unknown"}
- Country: {country or "unknown"}
- Conversation stage: {current_sales_stage or "new_lead"}
- Last 3 messages in conversation: {recent}

The message to classify:
{message_text}
"""
