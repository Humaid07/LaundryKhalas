# WhatsApp Agent Behaviour Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register 9 WhatsApp behaviour rules in the canonical `whatsapp_agent_rules.json`, load them into the live Sonnet prompt, fix the brand to "Laundry Khalas", and enforce short 1–3-message replies, no-unnecessary-CTA, a backend-approved 5–7 min discount follow-up, a silent conversion review, and backend-only pickup slots.

**Architecture:** New versioned `behaviour_rules` section in `config/whatsapp_agent_rules.json` + `rules.py` accessors; `booking_system_prompt()` renders rule text FROM that JSON. New pure services (`reply_segmentation`, `conversion_guard`, `hesitation`) validated in the backend; the `_process_reply` turn loops `_deliver` per segment. Reuse existing `negotiation`, `scheduled_followups`, `pending_tasks`, `customer_memory` engines — no new subsystems, no DB migration.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, pytest (pure-policy + scripted-fake-Anthropic harnesses), Sonnet-5 via `AnthropicProvider`.

## Global Constraints

- Brand spelling is exactly **`Laundry Khalas`** (two words, single-a) in every customer-facing string. Never `Laundry Khalaas`, never concatenated `LaundryKhalas`. The domain `laundrykhalas.com` (URL) is unchanged.
- Max **3** customer-facing WhatsApp messages per normal turn. Segments must be non-empty, non-duplicate, not one-word fragments, not mid-sentence splits.
- The AI never picks a discount percentage — `services/negotiation.py::plan_offer` is authoritative. Discount ceiling/margin floor unchanged.
- Do NOT change: published prices, facility fees, markup, discount ceilings/eligibility, min-order, photo, payment/Stripe/cash, service/repair definitions, complaint/refund escalation, routing weights, Express pricing/eligibility, customer-memory rules.
- No DB migration. Extra follow-up fields live in `scheduled_followups.payload` (jsonb).
- `rules.py` is `lru_cache`d → prod restart to reload (existing, documented).
- Tests must not call a live LLM or live DB. Use pure-policy unit tests and the scripted-fake-Anthropic harness (`tests/test_booking_tools.py` pattern). Run the full suite before each phase commit.

---

## PHASE 1 — Rules as loaded source-of-truth + brand + supersede pickup-time

### Task 1.1: Add the `behaviour_rules` section + fix brand in `whatsapp_agent_rules.json`

**Files:**
- Modify: `apps/whatsapp-agent/config/whatsapp_agent_rules.json`
- Test: `apps/whatsapp-agent/tests/test_behaviour_rules.py` (create)

**Interfaces:**
- Produces: JSON section `behaviour_rules` with `version`, `updated_at`, `rules[]` (each `{id, category, priority, active, version, updated_at, text, params?}`); top-level `brand_name = "Laundry Khalas"`.

- [ ] **Step 1: Write the failing test** — `tests/test_behaviour_rules.py`:

```python
import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "whatsapp_agent_rules.json"
EXPECTED_IDS = {
    "WHATSAPP_BRAND_NAME", "WHATSAPP_RESPONSE_LENGTH", "WHATSAPP_RESPONSE_SEGMENTATION",
    "WHATSAPP_NO_UNNECESSARY_CTA", "WHATSAPP_SOFT_CONVERSION_STYLE", "WHATSAPP_DISCOUNT_FOLLOWUP",
    "WHATSAPP_PICKUP_SLOT_SELECTION", "WHATSAPP_NO_OPEN_ENDED_PICKUP_TIME",
    "WHATSAPP_HUMAN_CONVERSION_ESCALATION",
}

def _cfg():
    return json.loads(CONFIG.read_text(encoding="utf-8"))

def test_brand_name_is_laundry_khalas():
    assert _cfg()["brand_name"] == "Laundry Khalas"

def test_no_double_a_typo_anywhere():
    assert "Khalaas" not in CONFIG.read_text(encoding="utf-8")

def test_all_nine_behaviour_rules_present_and_active():
    rules = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert set(rules) == EXPECTED_IDS
    assert all(r["active"] for r in rules.values())
    assert all(r["text"].strip() for r in rules.values())

def test_brand_rule_carries_param():
    rules = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert rules["WHATSAPP_BRAND_NAME"]["params"]["brand_name"] == "Laundry Khalas"

def test_segmentation_rule_max_three():
    rules = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert rules["WHATSAPP_RESPONSE_SEGMENTATION"]["params"]["max_segments"] == 3
```

- [ ] **Step 2: Run test to verify it fails** — `pytest tests/test_behaviour_rules.py -v` → FAIL (`brand_name` is "LaundryKhalas", no `behaviour_rules` key).

- [ ] **Step 3: Edit the JSON** — set `"brand_name": "Laundry Khalas"`; replace every customer-facing `LaundryKhalas` in `domain.description`, `domain.allowed_topics`, `domain.refusal_message`, `welcome.message` with `Laundry Khalas` (leave the `_note` developer comment as-is EXCEPT change any `Khalaas`→none exist there). Add the `behaviour_rules` section exactly as specified in the design spec §4.1 (all 9 rules).

- [ ] **Step 4: Run test to verify it passes** — `pytest tests/test_behaviour_rules.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add config/whatsapp_agent_rules.json tests/test_behaviour_rules.py` (defer commit to end of Phase 1 per Task 1.5).

### Task 1.2: `rules.py` accessors

**Files:**
- Modify: `apps/whatsapp-agent/rules.py`
- Test: `apps/whatsapp-agent/tests/test_behaviour_rules.py` (extend)

**Interfaces:**
- Produces: `rules.behaviour_rules() -> dict`; `rules.behaviour_rule_texts() -> list[str]` (active rules, `priority` desc then declaration order, each rule's `text`); `rules.brand_name() -> str`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_behaviour_rules.py`:

```python
import rules

def test_behaviour_rule_texts_active_priority_desc():
    texts = rules.behaviour_rule_texts()
    assert any("Laundry Khalas" in t for t in texts)
    assert any("1, 2, or at most 3" in t for t in texts)
    # highest priority (brand=100) renders before segmentation (89)
    brand_i = next(i for i, t in enumerate(texts) if 'Laundry Khalas' in t and 'never' in t.lower())
    seg_i = next(i for i, t in enumerate(texts) if "at most 3" in t)
    assert brand_i < seg_i

def test_brand_name_accessor():
    assert rules.brand_name() == "Laundry Khalas"
```

- [ ] **Step 2: Run** — `pytest tests/test_behaviour_rules.py -k "accessor or priority" -v` → FAIL (no such functions).

- [ ] **Step 3: Implement** — add to `rules.py`:

```python
def behaviour_rules() -> dict:
    return agent_rules().get("behaviour_rules", {})

def behaviour_rule_texts() -> list[str]:
    rs = [r for r in behaviour_rules().get("rules", []) if r.get("active", True)]
    rs.sort(key=lambda r: -int(r.get("priority", 0)))
    return [str(r["text"]).strip() for r in rs if str(r.get("text", "")).strip()]

def brand_name() -> str:
    return str(agent_rules().get("brand_name", "Laundry Khalas"))
```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit** — defer to Task 1.5.

### Task 1.3: Render behaviour rules into `booking_system_prompt()` + drop "exactly ONE message" + brand from rules

**Files:**
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (`_persona_intro` ~509, `booking_system_prompt` 545–859; lines 524/532/537 brand; 732/820 single-message)
- Test: `apps/whatsapp-agent/tests/test_behaviour_rules_prompt.py` (create)

**Interfaces:**
- Consumes: `rules.behaviour_rule_texts()`, `rules.brand_name()`.
- Produces: `booking_system_prompt()` output contains every active rule `text` and the brand "Laundry Khalas", and NO "exactly ONE" single-message directive.

- [ ] **Step 1: Write the failing test** — `tests/test_behaviour_rules_prompt.py`:

```python
from agents.whatsapp_agent.booking_tools import booking_system_prompt
import rules

def test_prompt_contains_all_active_behaviour_rules():
    prompt = booking_system_prompt()
    for text in rules.behaviour_rule_texts():
        # rule texts are rendered verbatim (first sentence is a stable anchor)
        anchor = text.split(".")[0]
        assert anchor in prompt, f"missing rule in prompt: {anchor!r}"

def test_prompt_uses_correct_brand_and_not_typo():
    prompt = booking_system_prompt()
    assert "Laundry Khalas" in prompt
    assert "Khalaas" not in prompt

def test_prompt_no_longer_forces_single_message():
    prompt = booking_system_prompt().lower()
    assert "exactly one concise confirmation" not in prompt
    assert "keep each reply to one short message" not in prompt

def test_prompt_allows_one_to_three_messages():
    assert "1, 2, or at most 3" in booking_system_prompt()
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement:**
  1. In `_persona_intro`/`booking_system_prompt`, replace the three `Laundry Khalaas` literals (524/532/537) so the persona intro reads brand from `rules.brand_name()` (e.g. build `brand = rules.brand_name()` and interpolate).
  2. Insert a rendered block near the writing-style section: `"\nBehaviour rules (authoritative — follow exactly):\n" + "\n".join(f"- {t}" for t in rules.behaviour_rule_texts()) + "\n"`.
  3. Replace the line 732 confirmation directive: change "Send exactly ONE concise confirmation with the order reference…" → "Send a concise confirmation (1–2 short messages) with the order reference, pickup date/time…" (keep the operational content; drop "exactly ONE").
  4. Replace line 820 "SHORT REPLIES: keep each reply to one short message, usually 5 to 25 words…" → "SHORT REPLIES: keep messages short (usually 5 to 25 words each); a reply may be 1–3 short messages per the behaviour rules, and ask at most one necessary question."

- [ ] **Step 4: Run** — `pytest tests/test_behaviour_rules_prompt.py -v` → PASS.

- [ ] **Step 5: Commit** — defer to Task 1.5.

### Task 1.4: Brand fix across remaining customer-facing modules + supersede pickup-time step

**Files:**
- Modify: `config/persona.json` (`organization`), `services/persona_assignment.py:92`, `services/followups.py:53`, `services/process_guide.py:3,42` (docstrings), `config/whatsapp_agent_rules.json` (`booking_flow.steps`)
- Modify tests that assert the old spelling: `tests/test_followups.py:136`, `tests/test_reply_style.py:30`, `tests/test_persona_assignment.py:118`
- Test: `apps/whatsapp-agent/tests/test_brand_spelling.py` (create)

**Interfaces:**
- Produces: no `Khalaas` anywhere in `apps/whatsapp-agent` runtime source; `booking_flow.steps` contains `select_pickup_slot`, not `select_pickup_time`.

- [ ] **Step 1: Write the failing test** — `tests/test_brand_spelling.py`:

```python
from pathlib import Path
import json, rules
from services import persona_assignment, followups

ROOT = Path(__file__).resolve().parent.parent

def test_no_khalaas_in_runtime_source():
    offenders = []
    for p in list(ROOT.glob("services/*.py")) + list(ROOT.glob("agents/whatsapp_agent/*.py")) + list(ROOT.glob("config/*.json")):
        if "Khalaas" in p.read_text(encoding="utf-8"):
            offenders.append(p.name)
    assert offenders == [], f"brand typo remains in: {offenders}"

def test_persona_org_is_correct():
    assert persona_assignment.assign_persona("+9715xxxxxxx")["organization"] == "Laundry Khalas" \
        if hasattr(persona_assignment, "assign_persona") else True
    assert json.loads((ROOT / "config" / "persona.json").read_text())["organization"] == "Laundry Khalas"

def test_followup_template_brand():
    assert "Laundry Khalas" in followups.render(followups.WEB_ABANDONMENT_1, persona="Zoya")
    assert "Khalaas" not in followups.render(followups.WEB_ABANDONMENT_1, persona="Zoya")

def test_pickup_time_step_superseded():
    steps = rules.agent_rules()["booking_flow"]["steps"]
    assert "select_pickup_time" not in steps
    assert "select_pickup_slot" in steps
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement** — replace `Laundry Khalaas`→`Laundry Khalas` in `persona.json:organization`, `persona_assignment.py:92`, `followups.py:53`, `process_guide.py:3,42`; in `whatsapp_agent_rules.json` change `booking_flow.steps` entry `"select_pickup_time"`→`"select_pickup_slot"`. Update the three existing tests' assertions to `Laundry Khalas`.

- [ ] **Step 4: Run** — `pytest tests/test_brand_spelling.py tests/test_followups.py tests/test_reply_style.py tests/test_persona_assignment.py -v` → PASS.

- [ ] **Step 5: (part of Task 1.5 commit)**

### Task 1.5: Phase 1 verification + commit

- [ ] **Step 1: Full suite** — `pytest -q -p no:cacheprovider` → all pass (report count).
- [ ] **Step 2: Grep guard** — `grep -rn "Khalaas" apps/whatsapp-agent/services apps/whatsapp-agent/agents apps/whatsapp-agent/config` → no output.
- [ ] **Step 3: Commit** —

```bash
git add apps/whatsapp-agent/config/whatsapp_agent_rules.json apps/whatsapp-agent/rules.py \
  apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py apps/whatsapp-agent/config/persona.json \
  apps/whatsapp-agent/services/persona_assignment.py apps/whatsapp-agent/services/followups.py \
  apps/whatsapp-agent/services/process_guide.py apps/whatsapp-agent/tests/test_behaviour_rules.py \
  apps/whatsapp-agent/tests/test_behaviour_rules_prompt.py apps/whatsapp-agent/tests/test_brand_spelling.py \
  apps/whatsapp-agent/tests/test_followups.py apps/whatsapp-agent/tests/test_reply_style.py \
  apps/whatsapp-agent/tests/test_persona_assignment.py
git commit -m "WhatsApp rules: behaviour_rules section loaded into prompt + brand→Laundry Khalas"
```

---

## PHASE 2 — Segmentation + no-CTA guard + soft style

### Task 2.1: `services/reply_segmentation.py`

**Files:**
- Create: `apps/whatsapp-agent/services/reply_segmentation.py`
- Test: `apps/whatsapp-agent/tests/test_reply_segmentation.py` (create)

**Interfaces:**
- Produces: `segment_reply(text: str, *, max_segments: int = 3, delimiter: str = "---") -> list[str]`.

- [ ] **Step 1: Write the failing test:**

```python
from services.reply_segmentation import segment_reply

def test_no_delimiter_returns_single():
    assert segment_reply("Clean and Press for 5 shirts is AED 45.") == ["Clean and Press for 5 shirts is AED 45."]

def test_two_segments():
    txt = "Yes, we clean suede shoes. Prices start from AED 50.\n---\nSend a photo for a better estimate, or we can collect and confirm after inspection."
    out = segment_reply(txt)
    assert len(out) == 2
    assert out[0].startswith("Yes, we clean suede")
    assert out[1].startswith("Send a photo")

def test_caps_at_three_merging_overflow():
    txt = "A. one.\n---\nB two.\n---\nC three.\n---\nD four."
    out = segment_reply(txt)
    assert len(out) == 3
    assert out[2].endswith("D four.")  # 4th merged into 3rd

def test_drops_empty_and_one_word_fragments():
    txt = "Yes, we collect from Dubai Marina.\n---\n \n---\nok"
    out = segment_reply(txt)
    assert out == ["Yes, we collect from Dubai Marina."]

def test_merges_mid_sentence_split():
    txt = "Prices start from AED 50 depending\n---\non the condition of the shoes."
    out = segment_reply(txt)
    assert out == ["Prices start from AED 50 depending on the condition of the shoes."]

def test_dedup_adjacent_identical():
    txt = "Yes, we collect from Marina.\n---\nYes, we collect from Marina."
    assert segment_reply(txt) == ["Yes, we collect from Marina."]
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement:**

```python
"""Split a model reply into 1-3 validated WhatsApp messages (spec §3/§20).

The model separates intended messages with a line containing only the
delimiter. The backend is authoritative: it trims, drops empty/one-word
fragments, dedups adjacent duplicates, refuses mid-sentence splits (merges
them), and caps the count by merging any overflow into the last segment.
"""
from __future__ import annotations

import re

_SENTENCE_END = (".", "?", "!", ":", "…")

def _looks_midsentence(prev: str, nxt: str) -> bool:
    if not prev or not nxt:
        return False
    return not prev.rstrip().endswith(_SENTENCE_END) or nxt.lstrip()[:1].islower()

def _is_fragment(seg: str) -> bool:
    s = seg.strip()
    return not s or len(s.split()) < 2

def segment_reply(text: str, *, max_segments: int = 3, delimiter: str = "---") -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(rf"(?m)^\s*{re.escape(delimiter)}\s*$", raw)
    segs: list[str] = []
    for part in parts:
        s = part.strip()
        if not s:
            continue
        if segs and (_is_fragment(s) or _looks_midsentence(segs[-1], s)):
            segs[-1] = f"{segs[-1]} {s}".strip()
            continue
        if _is_fragment(s):  # leading fragment with nothing to merge into
            if segs:
                segs[-1] = f"{segs[-1]} {s}".strip()
            continue
        if segs and segs[-1].strip() == s:  # dedup adjacent identical
            continue
        segs.append(s)
    if not segs:
        return [raw]
    while len(segs) > max_segments:
        segs[-2] = f"{segs[-2]} {segs.pop()}".strip()
    return segs
```

- [ ] **Step 4: Run** — `pytest tests/test_reply_segmentation.py -v` → PASS.

- [ ] **Step 5: Commit** — defer to Task 2.4.

### Task 2.2: `services/conversion_guard.py`

**Files:**
- Create: `apps/whatsapp-agent/services/conversion_guard.py`
- Test: `apps/whatsapp-agent/tests/test_conversion_guard.py` (create)

**Interfaces:**
- Produces: `is_conversion_cta(text: str) -> bool`; `recent_cta_count(agent_texts: list[str]) -> int`; `strip_trailing_cta(text: str) -> str`.

- [ ] **Step 1: Write the failing test:**

```python
from services.conversion_guard import is_conversion_cta, recent_cta_count, strip_trailing_cta

def test_detects_booking_ctas():
    for t in ["Would you like to proceed?", "Shall I book this for you?",
              "Would you like me to arrange pickup?", "Do you want to go ahead?"]:
        assert is_conversion_cta(t)

def test_operational_question_is_not_cta():
    for t in ["Please send me the pickup address.", "Which slot works better, 2 PM-4 PM or 5 PM-7 PM?",
              "The final price is AED 140. Shall I proceed with the work?"]:
        assert not is_conversion_cta(t)

def test_recent_cta_count():
    assert recent_cta_count(["24 hours. Would you like to book?", "Yes we collect from Marina."]) == 1

def test_strip_trailing_cta_removes_appended_sales_question():
    t = "Clean and Press for 5 shirts is AED 45. Would you like me to arrange the booking?"
    assert strip_trailing_cta(t) == "Clean and Press for 5 shirts is AED 45."

def test_strip_keeps_text_without_cta():
    t = "Yes, we collect from Dubai Marina."
    assert strip_trailing_cta(t) == t
```

- [ ] **Step 2: Run** — FAIL.

- [ ] **Step 3: Implement:**

```python
"""Detect and suppress unnecessary conversion CTAs (spec §4/§16).

An unnecessary CTA is a booking/sales question ("would you like to book?")
appended to an answer. Operational questions (address, pin, slot choice,
explicit price/quote approval) are NOT CTAs and are never stripped.
"""
from __future__ import annotations

import re

_CTA_PATTERNS = [
    r"would you like (me )?to (proceed|book|arrange|go ahead|order)",
    r"would you like to (proceed|book|order|go ahead)",
    r"shall i (book|arrange|order|go ahead)",
    r"do you want (me )?to (proceed|book|go ahead|arrange)",
    r"would you still like to proceed",
    r"ready to book",
    r"want to (book|proceed|go ahead)\??$",
]
# Operational approvals that LOOK like CTAs but are required next-step questions.
_OPERATIONAL = [
    r"shall i proceed with the work",
    r"final price is",
    r"which (slot|one|time)",
    r"please (send|share)",
]
_CTA_RE = re.compile("|".join(_CTA_PATTERNS), re.IGNORECASE)
_OP_RE = re.compile("|".join(_OPERATIONAL), re.IGNORECASE)

def is_conversion_cta(text: str) -> bool:
    t = (text or "").strip()
    if not t or _OP_RE.search(t):
        return False
    return bool(_CTA_RE.search(t))

def recent_cta_count(agent_texts: list[str]) -> int:
    return sum(1 for t in (agent_texts or []) if is_conversion_cta(t))

def strip_trailing_cta(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    # split into sentences; drop a trailing sentence that is a bare CTA
    sentences = re.split(r"(?<=[.?!])\s+", t)
    while sentences and is_conversion_cta(sentences[-1]):
        sentences.pop()
    return " ".join(sentences).strip() or t
```

- [ ] **Step 4: Run** — PASS.

- [ ] **Step 5: Commit** — defer to Task 2.4.

### Task 2.3: Wire segmentation + guard into `_process_reply`

**Files:**
- Modify: `apps/whatsapp-agent/api/evolution_webhooks.py` (deliver site ~802; history already at ~763)
- Test: `apps/whatsapp-agent/tests/test_turn_segmentation.py` (create)

**Interfaces:**
- Consumes: `reply_segmentation.segment_reply`, `conversion_guard.recent_cta_count`/`strip_trailing_cta`, existing `_deliver`.
- Produces: `_process_reply` delivers ≤3 ordered messages; when the turn is an info answer with no operational need and a recent CTA exists, a trailing CTA is stripped.

- [ ] **Step 1: Write the failing test** — drive the scripted-fake-Anthropic harness (mirror `tests/test_booking_tools.py`) with a reply containing a delimiter, asserting `_deliver` was called per segment in order. (Reuse `_FakeClient`/`_ctx`/`FakeOrdersRepo` helpers; assert on a captured deliveries list via monkeypatching `_deliver`.)

```python
# tests/test_turn_segmentation.py  (uses helpers copied from test_booking_tools.py)
import api.evolution_webhooks as wh
from services.reply_segmentation import segment_reply

def test_segment_reply_integration_orders_messages():
    txt = "Yes, we clean suede shoes. Prices start from AED 50.\n---\nSend a photo for a better estimate."
    segs = segment_reply(txt)
    assert segs[0].startswith("Yes, we clean suede") and segs[1].startswith("Send a photo")
```

(Full end-to-end delivery-loop assertion added using the existing fake-client harness; if that harness is heavy, keep this task's automated proof at the `segment_reply` + a `_deliver`-loop unit level and validate ordering via a monkeypatched capture list.)

- [ ] **Step 2: Run** — FAIL / RED as appropriate.

- [ ] **Step 3: Implement** — at `_process_reply` ~802 replace the single `_deliver` with:

```python
if live:
    agent_texts = [m.get("text", "") for m in history if m.get("role") == "assistant"][-4:]
    reply_out = reply_text
    # info-answer with no operational need + a recent CTA already asked -> trim a trailing sales CTA
    if conversion_guard.recent_cta_count(agent_texts) >= 1:
        trimmed = conversion_guard.strip_trailing_cta(reply_out)
        if trimmed:
            reply_out = trimmed
    segments = reply_segmentation.segment_reply(reply_out)
    for seg in segments:
        await _deliver(channel, phone, convo["id"],
                       booking_flow.BookingReply(text=seg, state=state),
                       turn_id=turn_id)
```

Add imports `from services import reply_segmentation, conversion_guard`. Ensure `history` message shape keys (`role`/`text`) match what `_build_history` produces; adapt accessor if different.

- [ ] **Step 4: Run** — `pytest tests/test_turn_segmentation.py tests/test_outbound_idempotency.py -v` → PASS (idempotency still green: distinct segment bodies → distinct keys).

- [ ] **Step 5: Commit** — defer to Task 2.4.

### Task 2.4: Extend tone avoid-list + Phase 2 verification + commit

**Files:**
- Modify: `apps/whatsapp-agent/config/agent_tone_rules.json` (`avoid`)
- Test: extend `tests/test_behaviour_rules_prompt.py`

- [ ] **Step 1: Test** — assert `build_system_prompt()` (prompts.py) contains a filler-avoidance directive and that `agent_tone_rules.json["avoid"]` includes `"unnecessary CTAs"` and filler words.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — append to `avoid`: `"filler words like Great/Perfect/Wonderful/Absolutely/Certainly/Thanks for sharing unless natural"`, `"unnecessary booking CTAs"`, `"routine exclamation marks"`.
- [ ] **Step 4: Run full suite** — `pytest -q -p no:cacheprovider` → all pass.
- [ ] **Step 5: Commit** —

```bash
git add apps/whatsapp-agent/services/reply_segmentation.py apps/whatsapp-agent/services/conversion_guard.py \
  apps/whatsapp-agent/api/evolution_webhooks.py apps/whatsapp-agent/config/agent_tone_rules.json \
  apps/whatsapp-agent/tests/test_reply_segmentation.py apps/whatsapp-agent/tests/test_conversion_guard.py \
  apps/whatsapp-agent/tests/test_turn_segmentation.py apps/whatsapp-agent/tests/test_behaviour_rules_prompt.py
git commit -m "WhatsApp: 1-3 message segmentation + no-unnecessary-CTA guard + soft-style tone"
```

---

## PHASE 3 — Discount objection + 5–7 min follow-up + conversion review + hesitation

### Task 3.1: `services/hesitation.py` (deterministic price signals)

**Files:**
- Create: `apps/whatsapp-agent/services/hesitation.py`
- Test: `apps/whatsapp-agent/tests/test_hesitation.py`

**Interfaces:**
- Produces: `is_price_enquiry(text) -> bool`; `is_price_objection(text) -> bool`. (Discount request = existing `negotiation.detect_discount_request`.)

- [ ] **Step 1: Test:**

```python
from services.hesitation import is_price_enquiry, is_price_objection

def test_price_enquiry_not_objection():
    assert is_price_enquiry("How much for 5 shirts?")
    assert not is_price_objection("How much for 5 shirts?")

def test_real_objection():
    assert is_price_objection("That's too expensive.")
    assert is_price_objection("that is way too much")
    assert not is_price_enquiry("That's too expensive.")
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — phrase matchers: enquiry = `how much|what.*price|what.*cost|rate for|price for`; objection = `too expensive|too much|expensive|cheaper|that's a lot|pricey|over my budget`. Objection wins if both match. Keep pure/simple.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** — defer to 3.5.

### Task 3.2: `DISCOUNT_OBJECTION` follow-up type + config + scheduling helper

**Files:**
- Modify: `apps/whatsapp-agent/services/followups.py` (type constant, template, `_families`), `apps/whatsapp-agent/config/followups.json` (offset+priority), `apps/whatsapp-agent/services/followup_scheduler.py` (builder)
- Test: `apps/whatsapp-agent/tests/test_followups.py` (extend), `tests/test_followup_scheduler.py` (extend)

**Interfaces:**
- Produces: `followups.DISCOUNT_OBJECTION`; `followup_scheduler.discount_objection_row(*, conversation_id, order_id, customer_phone, anchor_at, market, persona, quote_version, trigger_message_id) -> dict`.

- [ ] **Step 1: Tests** — assert offset for `DISCOUNT_OBJECTION` is 6 (∈ [5,7]); the builder yields a row with `followup_type="DISCOUNT_OBJECTION"`, `due_at == anchor + 6min` (shifted into window), stable `dedupe_key == "conv:DISCOUNT_OBJECTION:<anchor>"`, and `payload` carrying `quote_version`+`trigger_message_id`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — add constant + template (`"I checked again — {offer}"` style is set at send time, so template is a neutral placeholder), add `"DISCOUNT_OBJECTION": 6` to `offsets_minutes` and into `priority` (above WEB_ABANDONMENT_1), add builder mirroring `quote_inactivity_row` but writing `payload={"quote_version":…, "trigger_message_id":…, "trigger_type":"DISCOUNT_OBJECTION"}`.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** — defer to 3.5.

### Task 3.3: Schedule on decline + send-time recheck via `negotiation.plan_offer`

**Files:**
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (negotiate handler ~1578–1633: on no-immediate-offer, schedule DISCOUNT_OBJECTION), `apps/whatsapp-agent/services/followups.py` (`SuppressionContext` + `is_suppressed` discount branch), `apps/whatsapp-agent/scripts/run_due_followups.py` (`_suppression_context` + send: for DISCOUNT_OBJECTION compute offer via `negotiation.plan_offer`)
- Test: `tests/test_followups.py`, `tests/test_discount_followup.py` (create)

**Interfaces:**
- Consumes: `negotiation.plan_offer`, `scheduled_followups_repo.schedule`.
- Produces: send-time behaviour — offer available → send backend offer; else suppress (reason) + trigger review (Task 3.4).

- [ ] **Step 1: Tests** — pure tests: (a) `is_suppressed(DISCOUNT_OBJECTION, ctx)` suppresses on `customer_replied/human_takeover/order_confirmed/paid/opted_out/order_cancelled`; (b) a helper `discount_followup_decision(order_state) -> ("send", offer) | ("suppress", reason) | ("review", reason)` returns `send` when `plan_offer` yields `offer_ladder`, `review` when `escalate`, `suppress` when quote_version changed. Unit-test that helper directly with fake order states.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — add `discount_followup_decision(...)` (pure, in `services/followups.py` or a new `services/discount_followup.py`) wrapping `negotiation.plan_offer`; schedule on decline in the negotiate handler when action is `escalate`/no-offer AND customer hasn't accepted; wire the sweeper to call the decision and send the offer text or suppress.
- [ ] **Step 4: Run** — `pytest tests/test_discount_followup.py tests/test_followups.py -v` → PASS.
- [ ] **Step 5: Commit** — defer to 3.5.

### Task 3.4: `CUSTOMER_CONVERSION_REVIEW` pending-task (silent, deduped)

**Files:**
- Modify: `apps/whatsapp-agent/services/pending_tasks.py` (`TASK_TYPES`, SLA), `apps/whatsapp-agent/config/pending_tasks.json` (SLA entry), `apps/whatsapp-agent/services/negotiation_review.py` (create: build context + create task with one-active-per-conversation dedupe)
- Test: `tests/test_conversion_review.py` (create)

**Interfaces:**
- Produces: `negotiation_review.flag_conversion_review(*, conversation_id, customer_id, order_id, reason, context) -> bool` (True if created, False if an open one already exists).

- [ ] **Step 1: Tests** — with a fake `pending_tasks_repo`: first call creates a `CUSTOMER_CONVERSION_REVIEW` task with `reason` and internal context in `notes`; second call (open task exists) returns False (no duplicate). Assert customer context fields present; assert NO conversation pause call.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — add `CUSTOMER_CONVERSION_REVIEW` to `TASK_TYPES` + SLA config; `flag_conversion_review` queries open tasks for the conversation, inserts if none, stores reason ∈ `{DISCOUNT_LIMIT_REACHED, PRICE_OBJECTION_MARGIN_LIMIT, CUSTOMER_CONVERSION_REVIEW}` in `escalation_rule`, packs context (service, price, existing discount, max discount, facility cost, recent messages, hesitation reason, state) into `notes`. No `start_human_takeover`.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** — defer to 3.5.

### Task 3.5: Phase 3 verification + commit

- [ ] **Step 1: Full suite** — `pytest -q -p no:cacheprovider` → all pass.
- [ ] **Step 2: Commit** —

```bash
git add apps/whatsapp-agent/services/hesitation.py apps/whatsapp-agent/services/followups.py \
  apps/whatsapp-agent/services/followup_scheduler.py apps/whatsapp-agent/config/followups.json \
  apps/whatsapp-agent/scripts/run_due_followups.py apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py \
  apps/whatsapp-agent/services/pending_tasks.py apps/whatsapp-agent/config/pending_tasks.json \
  apps/whatsapp-agent/services/negotiation_review.py apps/whatsapp-agent/services/discount_followup.py \
  apps/whatsapp-agent/tests/test_hesitation.py apps/whatsapp-agent/tests/test_discount_followup.py \
  apps/whatsapp-agent/tests/test_conversion_review.py apps/whatsapp-agent/tests/test_followups.py \
  apps/whatsapp-agent/tests/test_followup_scheduler.py
git commit -m "WhatsApp: 5-7min discount-objection follow-up + silent conversion review"
```

---

## PHASE 4 — Pickup enforcement + tests

### Task 4.1: Address+pin-first enforcement (ask only the missing piece)

**Files:**
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (pickup guidance / next-step prompt; reads `customer_memory.shape_saved_address(...).pin_available`)
- Test: `tests/test_pickup_enforcement.py` (create)

**Interfaces:**
- Consumes: `customer_memory.shape_saved_address`, existing `pickup_availability`/`slots_repo`.
- Produces: prompt/next-step logic that asks only for the missing address OR pin, then presents slots.

- [ ] **Step 1: Tests** — pure/prompt-level: `booking_system_prompt()` contains the pickup rule text and no "what pickup time"/"when would you like" phrasing; a helper `next_location_ask(saved_addr)` returns `"pin"` when address present & `pin_available False`, `"address"` when pin present & no typed address, `None` when both present.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — add `next_location_ask(shaped_addr) -> str|None` (pure) and reference it in the pickup guidance; ensure prompt has no open-ended-time phrasing.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** — defer to 4.3.

### Task 4.2: Slot presentation + no-slot fallback assertions

**Files:**
- Test: `tests/test_pickup_enforcement.py` (extend), leaning on existing `pickup_availability`
- Modify (only if a gap surfaces): `agents/whatsapp_agent/booking_tools.py` slot-tool guidance

**Interfaces:**
- Consumes: `pickup_availability.get_availability` (returns slots + `next_available_date`).

- [ ] **Step 1: Tests** — with a fake `slots_provider`: when slots exist, the availability result exposes them with stable `slot_id`s (agent presents them + "which works better?"); when empty, `next_available_date` is populated (fallback, no fabricated time). Assert the necessary CTA "which works better?" is NOT stripped by `conversion_guard.is_conversion_cta` (already covered in 2.2 but assert here in the pickup context). Reference routing-layer Tests 18/19 as satisfied by existing `tests/test_routing_*`/`routing/slots.py` (add/point to a test asserting `earliest_slot` excludes windows with no available driver).
- [ ] **Step 2–4:** Run; implement only if a gap appears; PASS.
- [ ] **Step 5: Commit** — defer to 4.3.

### Task 4.3: Phase 4 verification + commit

- [ ] **Step 1: Full suite** — `pytest -q -p no:cacheprovider` → all pass.
- [ ] **Step 2: Commit** —

```bash
git add apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py apps/whatsapp-agent/tests/test_pickup_enforcement.py
git commit -m "WhatsApp: pickup enforcement — address+pin first, backend slots, no open-ended time"
```

---

## Final documentation task (after Phase 4)

- [ ] Write `docs/build-reports/2026-08-08-whatsapp-behaviour-corrections.md` (25-point build report per CLAUDE.md §12), update `docs/00-Home.md`, and note the deferred driver-grounded customer-slot wiring (spec §7). Run full suite; record honest results. Commit.

## Self-review notes (coverage map)
- §1 rules registration → Task 1.1/1.2; §2 brand → 1.1/1.3/1.4; §3 segmentation → 2.1/2.3; §4/§5/§16 no-CTA → 2.2/2.3; §6/§19 soft style → 1.3/2.4; §7 decline → 3.3; §8 5–7min follow-up → 3.2/3.3; §9/§18 review → 3.4; §10/§13/§14 pickup → 1.4/4.1/4.2; §11 address+pin → 4.1; §17 hesitation → 3.1; §20 structured output → 2.1/2.3; §21 follow-up state → 3.2 (payload mapping); §22 source-of-truth → 1.1–1.3; §23 versioning → 1.1; §24 invariants → Global Constraints; §25 tests → per task; §26 supersede → 1.4. Tests 1–17,20–28 mapped; Tests 18/19 satisfied at the routing-engine layer (documented limitation, spec §7).
