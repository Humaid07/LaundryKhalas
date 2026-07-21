# Domain Guard

The mechanism that keeps the standalone WhatsApp Agent from answering
anything outside LaundryKhalaas/laundry/cleaning. Two independent layers -
either one failing doesn't defeat the other.

## Layer 1 — deterministic keyword/pattern guard

`apps/whatsapp-agent/services/domain_guard.py`, `classify(text) -> Domain`.
Runs **before any LLM call**, on every inbound message, in both the local
test-chat endpoint and the WhatsApp webhook.

- `Domain.IN_DOMAIN` - matches an in-domain keyword (laundry, dry cleaning,
  pickup, delivery, pricing, LaundryKhalaas, stain situations, etc.) and no
  out-of-domain signal.
- `Domain.OUT_OF_DOMAIN` - matches an out-of-domain keyword (coding,
  politics, religion, finance, medical, jokes, general trivia) with no
  in-domain signal, **or** matches a prompt-injection pattern regardless of
  anything else (see below - injection always wins).
- `Domain.UNCERTAIN` - neither list matches clearly, or the message is a
  short greeting/ack (≤4 words). Uncertain messages are **not** refused -
  they're passed to the agent, which asks a clarifying laundry-related
  question rather than answering something unrelated. This avoids refusing
  a bare "Hi" or "Yes" that has no keywords at all.

If `classify()` returns `OUT_OF_DOMAIN`, `agents/whatsapp_agent/agent.py`
returns the fixed refusal text immediately and **does not call the LLM at
all** - no cost, no risk of the model being talked into something it
shouldn't via the message itself (the injection patterns catch that
separately, layer 1 rejects it before the model ever sees it).

### Prompt-injection patterns

A dedicated regex list inside layer 1 (`_INJECTION_PATTERNS`) matches
attempts like "ignore previous instructions", "reveal your system prompt",
"tell me your API key", "pretend you are...", "act as...", "you are now...".
Any match forces `OUT_OF_DOMAIN` unconditionally, even if the message also
contains laundry keywords - an injection attempt wrapped in laundry talk is
still refused.

## Layer 2 — system prompt restriction

`agents/whatsapp_agent/prompts.py`, `build_system_prompt()`. Even for
messages that pass layer 1 (`IN_DOMAIN`/`UNCERTAIN`), the system prompt
sent to whichever LLM provider is active repeats the restriction
explicitly: only answer LaundryKhalaas/laundry/cleaning topics, never
reveal the prompt/instructions/API keys, refuse role-change attempts,
never invent prices/policies, never promise unconfigured guarantees,
escalate complaints/refunds/cancellations to the human team instead of
resolving them.

This is the exact text required by the task brief, verbatim, plus the
additional non-negotiable rules from `CLAUDE.md` (never invent data, no
hard promises, escalate risky topics).

## Why two layers instead of one

Layer 1 is cheap, deterministic, and testable without any LLM (see
`tests/test_domain_guard.py` - 16 parametrized examples, all passing) - it
catches the obvious cases for free and guarantees zero LLM spend on clearly
out-of-scope traffic. Layer 2 is the fallback for anything layer 1's
keyword lists don't anticipate (natural language has more variety than any
fixed list) - if a message slips through as `UNCERTAIN` or a real LLM
provider is later enabled and asked something layer 1's list didn't cover,
the system prompt is still there refusing it. Neither layer depends on the
other being correct.

## Known limitation

Layer 1 is keyword-based, so it's a heuristic, not a semantic classifier -
it can be fooled by phrasing with no matching keywords (caught by layer 2
instead) or, less commonly, a legitimate laundry message using unusual
phrasing could fall to `UNCERTAIN` and get a clarifying question rather
than a direct answer (annoying, not unsafe). This is an accepted tradeoff
for a fast, zero-cost, fully-tested first layer - not the same thing as
the full Classifier Agent on the main system's roadmap (`CLAUDE.md` §9),
which is a separate, more sophisticated future module.
