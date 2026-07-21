# Privacy Firewall

## Rule

Customer phone number, email, and full address must never reach:
- an LLM prompt, or
- a facility-facing output.

Area/city are acceptable substitutes for full address wherever logistics
reasoning is needed.

## Implementation

All of this lives in `app/services/privacy.py`:

- `mask_phone(text)` / `mask_email(text)` / `mask_pii(text)` - regex-based
  redaction for free text (used for logging/inspection, not for the
  structured LLM-context path below).
- `safe_address_for_llm(area, city, address_text=None)` - returns
  `"area, city"` and deliberately never returns `address_text`.
- `customer_context_for_llm(name, area, city, preferred_language)` - the
  *only* function that should ever build the customer-related portion of an
  LLM prompt. It returns `{"name", "area_city", "preferred_language"}` -
  structurally, there is no phone/email/address field for a caller to
  accidentally include.
- `facility_facing_order_view(order)` - strips `customer_phone`,
  `customer_email`, and `address_text` from any dict representing an order
  before it could be shown to a facility. `address_text` is only included
  if the caller explicitly sets `include_full_address=True` on the input
  (there is no such caller in this codebase yet - facility-facing endpoints
  are future work).

## Where it's enforced in the agent flow

`agents/whatsapp_operations/graph.py::draft_reply` builds its prompt context
exclusively via `customer_context_for_llm(...)` - it has access to the full
`Customer` row (including phone) in `state`, but only pulls `name` and
`slots["area"]` out of it. There is no code path in the happy-path agent
that passes a phone number, email, or full address string into
`llm_service.complete()`.

## Tests

`app/tests/test_privacy.py` covers:
- phone masking
- email masking
- combined PII masking
- `customer_context_for_llm` never contains an `@` or a phone-shaped string
- `facility_facing_order_view` drops contact fields even when the input
  dict contains them

## Known gaps / future work

- `mask_phone`/`mask_pii` are regex-based and not exhaustively tested
  against every international phone format - good enough for masking in
  logs, not a guarantee for compliance-grade redaction.
- There is no facility-facing API endpoint in this task at all (no
  facility-side flows exist yet), so `facility_facing_order_view` is
  exercised only by its unit test, not by a live route. Any future
  facility-facing endpoint MUST use it.
- AIActionLog and OrderEvent rows currently store full tool inputs/outputs
  (including e.g. phone numbers) for admin traceability - this is
  intentional (the admin panel is not the LLM and not facility-facing,
  and admins already have legitimate access to customer contact details),
  but should be revisited under real RBAC before live launch.
