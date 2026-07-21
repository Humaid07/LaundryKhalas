# Test-Data Strategy

> This documents how LaundryKhalas keeps **seeded/demo data** clearly separated
> and safely resettable in the **dev/test Supabase project**. Related:
> [[supabase-dev-database]], [[whatsapp-agent-dashboard-inbox]].

## Principle

Even though the current Supabase project is dev/test-only, **every seeded row is
explicitly marked** so it can never be mistaken for real data and can always be
removed without touching anything else. This same discipline carries forward to
production later (where real rows will simply have the markers `false`).

## Marker columns (on every business table)

| column             | type    | meaning                                         |
|--------------------|---------|-------------------------------------------------|
| `is_test_data`     | boolean | row is test data (not a real customer/order)    |
| `is_demo`          | boolean | row is demo content for showcasing/reports      |
| `environment`      | text    | logical env, e.g. `dev`                          |
| `seed_batch_id`    | text    | which seed run created it                        |
| `seed_source`      | text    | who/what seeded it                               |
| `test_scenario_id` | text    | links a row to a scenario fixture               |
| `created_by_seed`  | boolean | created by a seed script (vs. app runtime)      |

Tables: `customers`, `conversations`, `messages`, `orders`, `order_events`,
`agent_flags`, `human_takeovers`, `approval_queue`, `tickets`, `agent_logs`.

## Canonical seed batch

```
is_test_data     = true
is_demo          = true
environment      = 'dev'
seed_source      = 'whatsapp_agent_test_seed'
seed_batch_id    = '20260721_whatsapp_agent_seed_v1'
created_by_seed  = true
```

Seeded content (see `supabase/migrations/20260721_000002_...sql`): 6 customers,
6 conversations (booking / refund-urgent / damaged / track / B2B / payment),
18 messages, 5 orders (`LK-AE-1024/1025/1026/1027/2031`), 5 agent flags, 2 human
takeovers, 3 tickets, 2 approvals, 3 order events, 4 agent logs. All PKs are
fixed literals → seeding is idempotent (`on conflict do nothing`).

## Scenario fixtures

`apps/whatsapp-agent/test-data/scenarios/*.json` (37 scenarios across 9 files:
booking, refund, complaint, damaged_item, missing_item, payment_issue, b2b,
out_of_domain, prompt_injection). Each scenario has: `scenario_id`, `category`,
`customer_message`, `expected_intent`, `expected_sentiment`, `expected_urgency`,
`expected_human_intervention_required`, `expected_dashboard_flag`,
`expected_short_reply`, `linked_demo_order_id`, `expected_team_routing`,
`forbidden_actions`. Reusable for classifier tests, agent-behaviour tests,
dashboard-alert tests, and regression tests.

## Seeding & resetting (guarded)

Scripts in `apps/whatsapp-agent/scripts/` refuse to run unless the environment is
unambiguously dev/test:

- **seed** requires `ALLOW_TEST_SEED=true`, `DATABASE_ENV=test`,
  `APP_ENV != production`, `SUPABASE_PROJECT_TYPE=test`, `DATABASE_MODE=supabase`.
  If `APP_ENV=production` it aborts with:
  *"Refusing to seed test data into production environment."*
- **reset** requires `ALLOW_TEST_RESET=true` + the same env gates, and deletes
  **only** rows where `is_test_data = true AND created_by_seed = true` (scoped to
  the seed batch by default). It never truncates and never deletes rows where
  `is_test_data = false`. Deletion runs child-before-parent for FK safety.

The guard logic lives in `scripts/_safety.py` (pure functions) and is unit-tested
in `tests/test_supabase_safety.py`.

## Dashboard surfacing

Seeded/demo conversations render **Test Data** and **Demo Conversation** badges in
the inbox (driven by `is_test_data` / `is_demo`), so operators always know a
thread is not a real customer.
