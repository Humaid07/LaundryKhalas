# Facility Privacy Firewall

The facility (partner) dashboard must never expose customer PII or another facility's data. This is enforced in the **backend** (structurally + tested), not just hidden in the UI.

## What a facility CAN see
- Order business id, service / item summary + breakdown (name + qty)
- **Area / city only** (never the full pickup address)
- Operational / cleaning instructions relevant to the order
- SLA / turnaround (turnaround text, estimated delivery, express eligibility)
- Order status + issue status
- Assigned driver/runner **label** (name only)
- Facility order value ("Completed Service Value") — customer order value attributed to the facility
- A customer **first-name label** (or "Customer")

## What a facility must NEVER see
- Customer full phone number, email, or full identity
- Full customer address
- Customer payment/card details or payment method
- Private customer complaint notes / internal platform notes
- Any other facility's orders, issues, finance, team, or settings

## How it's enforced
1. **Per-facility scoping** — every facility endpoint is guarded by `api/deps.py::require_facility_scope`, which resolves the caller's `facility_id` from their JWT claim (a facility user is locked to their own facility). Because the backend connects with the service role (RLS is bypassed), isolation lives in **application SQL**: every facility query includes `where facility_id = $1`. A client-supplied `facility_id` is never trusted. Cross-facility reads return 404/empty.
2. **PII-safe serializer** — `facility_orders_repo.to_facility_read()` returns only the operational fields above; customer name is reduced to a first-name label, and `customer_id`/`conversation_id`/phone/email/address/payment keys are omitted entirely. A test (`test_facility_serializer_excludes_pii`) asserts those keys are absent.
3. **Issues** store area/city + order business id only — never customer contact data.
4. **Notifications** never include full address or phone; contact numbers are stored full backend-only and shown masked (`services/privacy.mask_phone`).

## Related
[[facility-dashboard]] · [[facility-notifications]] · [[privacy-firewall]] (platform-wide)
