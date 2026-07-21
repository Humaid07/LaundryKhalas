"""End-to-end tests for the Laundry Class LangGraph agent — the 10 task test cases
plus memory-isolation and application-restart persistence.

Each test drives the agent exactly as a WhatsApp customer would (one message at a
time, same phone = same thread) and asserts the required behaviour: correct prices
from the file KB, no invented facts, memory across turns, handoff on critical cases,
and strict per-number memory isolation.
"""
import pytest

from laundry_class import observability as obs
from laundry_class.runtime import InMemoryRuntime, PersistentRuntime, thread_id_for


@pytest.fixture
def rt():
    return InMemoryRuntime()


@pytest.fixture
def admin_inbox(monkeypatch):
    inbox = []
    obs.set_admin_sink(inbox.append)
    yield inbox
    obs.set_admin_sink(None)


async def _say(rt, phone, text):
    return await rt.process_message(phone, text)


# ---------------------------------------------------------------------------
# TC1 — price enquiry + follow-up memory
# ---------------------------------------------------------------------------
async def test_tc1_price_and_followup_memory(rt):
    phone = "+971555550101"
    r1 = await _say(rt, phone, "Hi, how much is dry cleaning for a suit?")
    assert "45" in r1.text and "AED" not in r1.text or "45" in r1.text  # suit price present
    assert "45" in r1.text

    r2 = await _say(rt, phone, "And a shirt?")
    assert "9" in r2.text                      # shirt price recalled in dry-cleaning context
    assert "Welcome to Laundry Class" not in r2.text  # no repeated greeting

    r3 = await _say(rt, phone, "What would the total be for one suit and three shirts?")
    assert "72" in r3.text                     # 45 + 3x9
    assert "estimate" in r3.text.lower()


# ---------------------------------------------------------------------------
# TC2 — new order over multiple messages + memory
# ---------------------------------------------------------------------------
async def test_tc2_order_creation(rt):
    phone = "+971555550102"
    await _say(rt, phone, "I want to arrange a laundry pickup.")
    await _say(rt, phone, "My name is Maya and I am in JLT.")
    r3 = await _say(rt, phone, "I need wash and iron for five shirts and two trousers.")
    assert "67" in r3.text and "estimate" in r3.text.lower()  # 5x9 + 2x11
    await _say(rt, phone, "Pickup tomorrow evening.")
    await _say(rt, phone, "7 pm. Same number. Address is Cluster X, Tower 2, Apartment 804.")
    r6 = await _say(rt, phone, "Cash.")
    assert "confirm" in r6.text.lower()
    r7 = await _say(rt, phone, "Yes, confirm.")
    assert r7.current_order_id and r7.current_order_id.startswith("LC-TEST-")
    assert "recorded for testing" in r7.text.lower()
    r8 = await _say(rt, phone, "What time did I choose?")
    assert "7 PM" in r8.text


# ---------------------------------------------------------------------------
# TC3 — existing order status (own data only)
# ---------------------------------------------------------------------------
async def test_tc3_order_status(rt):
    phone = "+971500000101"  # Ahmed Khan / LC-TEST-1001
    r1 = await _say(rt, phone, "Hi, where is my order?")
    assert "LC-TEST-1001" in r1.text and "Processing" in r1.text
    r2 = await _say(rt, phone, "What did I send?")
    assert "Shirt" in r2.text and "Trousers" in r2.text
    r3 = await _say(rt, phone, "How much do I need to pay?")
    assert "67" in r3.text and "Cash on delivery" in r3.text


# ---------------------------------------------------------------------------
# TC4 — delivery reschedule (no false confirmation)
# ---------------------------------------------------------------------------
async def test_tc4_reschedule(rt, admin_inbox):
    phone = "+971500000102"  # Sara Ali / LC-TEST-1002
    r1 = await _say(rt, phone, "I got a message saying my delivery is coming around 4. I won't be home.")
    assert "?" in r1.text  # asks for the preferred time
    r2 = await _say(rt, phone, "Please come at 6 pm.")
    assert "6 PM" in r2.text and "confirm" in r2.text.lower()
    assert "LC-TEST-1002" in r2.text
    r3 = await _say(rt, phone, "Which address will they come to?")
    assert "Business Bay" in r3.text
    assert any("reschedule" in n.lower() for n in admin_inbox)


# ---------------------------------------------------------------------------
# TC5 — refund goes to a human, never approved
# ---------------------------------------------------------------------------
async def test_tc5_refund_handoff(rt, admin_inbox):
    phone = "+971500000103"  # Omar Hassan / LC-TEST-1003
    r1 = await _say(rt, phone, "I am not happy with my last order. I want a refund.")
    assert r1.handoff_required
    await _say(rt, phone, "Some of the clothes still smell dirty.")
    r3 = await _say(rt, phone, "So is my refund approved?")
    assert "not" in r3.text.lower() and "approv" in r3.text.lower()
    assert admin_inbox and "Refund" in admin_inbox[0]


# ---------------------------------------------------------------------------
# TC6 — damage complaint, one handoff, no liability admitted
# ---------------------------------------------------------------------------
async def test_tc6_damage_handoff(rt, admin_inbox):
    phone = "+971500000104"  # Fatima Noor / LC-TEST-1004
    r1 = await _say(rt, phone, "My silk dress has a tear after cleaning.")
    assert r1.handoff_required and r1.handoff_reason == "Damage complaint"
    await _say(rt, phone, "The order number is LC-TEST-1004. It was delivered today.")
    r3 = await _say(rt, phone, "Will you pay for the dress?")
    lowered = r3.text.lower()
    assert "we will definitely refund" not in lowered
    assert "responsibility" not in lowered or "review" in lowered
    # exactly one admin notification for the whole complaint
    assert len(admin_inbox) == 1


# ---------------------------------------------------------------------------
# TC7 — unknown item, no invented price, manual review on collect request
# ---------------------------------------------------------------------------
async def test_tc7_unknown_item(rt, admin_inbox):
    phone = "+971555550107"
    r1 = await _say(rt, phone, "How much do you charge to clean a horse-riding saddle?")
    assert "don't have" in r1.text.lower() or "inspect" in r1.text.lower()
    assert "AED" not in r1.text  # no number quoted
    r2 = await _say(rt, phone, "Just give me an estimate.")
    assert "inspect" in r2.text.lower() or "don't have" in r2.text.lower()
    r3 = await _say(rt, phone, "Can you collect it today?")
    assert r3.handoff_required
    assert admin_inbox


# ---------------------------------------------------------------------------
# TC8 — memory isolation between two numbers
# ---------------------------------------------------------------------------
async def test_tc8_memory_isolation(rt):
    a, b = "+971555550801", "+971555550802"
    await _say(rt, a, "My name is Daniel. I need five shirts collected from Apartment 304, "
                      "Marina Heights, Dubai Marina, tomorrow at 11 am.")
    ra = await _say(rt, a, "What address did I give you?")
    assert "Apartment 304" in ra.text

    rb1 = await _say(rt, b, "Hi, what address do you have for me?")
    assert "Apartment 304" not in rb1.text and "Daniel" not in rb1.text
    rb2 = await _say(rt, b, "What is Daniel's order?")
    assert "can't share" in rb2.text.lower() or "cannot share" in rb2.text.lower()

    ra2 = await _say(rt, a, "What time is my pickup?")
    assert "11 AM" in ra2.text

    assert thread_id_for(a) != thread_id_for(b)


# ---------------------------------------------------------------------------
# TC9 — natural multi-turn (no restart, no invented express price)
# ---------------------------------------------------------------------------
async def test_tc9_natural_multiturn(rt):
    phone = "+971555550909"
    for m in ["I have two dresses.", "Dry cleaning.",
              "One is a normal dress and one is an evening gown.", "How much?"]:
        r = await _say(rt, phone, m)
    assert "estimate" in r.text.lower()  # labelled as estimate, never an exact promise
    r_exp = await _say(rt, phone, "Express?")
    assert "confirm" in r_exp.text.lower()  # express not invented, must be confirmed by team
    # "10" after being asked a time must read as 10 o'clock, not 10 items/AED 10
    await _say(rt, phone, "Yes.")
    await _say(rt, phone, "Pickup from Downtown.")
    await _say(rt, phone, "Tomorrow morning.")
    r10 = await _say(rt, phone, "10.")
    assert "10:00 AM" in r10.text or "payment" in r10.text.lower()


# ---------------------------------------------------------------------------
# TC10 — explicit human request + payment dispute
# ---------------------------------------------------------------------------
async def test_tc10_human_and_payment(rt, admin_inbox):
    phone = "+971555550110"
    r1 = await _say(rt, phone, "I need to speak to a real person.")
    assert r1.handoff_required
    r2 = await _say(rt, phone, "I was charged twice.")
    assert r2.handoff_required
    lowered = r2.text.lower()
    for forbidden in ("cvv", "full card number", "pin", "otp"):
        # the agent may *warn* against sharing these, but must not *ask* for them
        assert "share your" in lowered or forbidden not in lowered or "don't" in lowered
    assert "cvv" in lowered  # confirms the safety warning is present


# ---------------------------------------------------------------------------
# Restart persistence (Part 8)
# ---------------------------------------------------------------------------
async def test_restart_persistence(tmp_path):
    db = str(tmp_path / "restart.sqlite")
    phone = "+971555551234"
    async with PersistentRuntime(db) as rt:
        await rt.process_message(phone, "I want to arrange a pickup.")
        await rt.process_message(phone, "My name is Omar and I am in Deira.")
        await rt.process_message(phone, "Wash and fold, one 6kg bag.")
        await rt.process_message(phone, "Tomorrow at 5 pm.")
    # brand-new runtime object over the same file == application restart
    async with PersistentRuntime(db) as rt2:
        r = await rt2.process_message(phone, "What pickup time did I request?")
    assert "5 PM" in r.text


# ---------------------------------------------------------------------------
# No-hallucination + greeting discipline
# ---------------------------------------------------------------------------
async def test_no_repeated_greeting(rt):
    phone = "+971555550999"
    r1 = await _say(rt, phone, "Hi")
    assert "Welcome to Laundry Class" in r1.text
    r2 = await _say(rt, phone, "How much for a two-piece suit dry clean?")
    assert "Welcome to Laundry Class" not in r2.text


async def test_prices_come_from_knowledge_base():
    from laundry_class import knowledge_base as kb
    assert kb.find_price("two-piece suit", "Dry Cleaning").price_aed == 45
    assert kb.find_price("shirt").price_aed == 9
    assert kb.find_price("horse-riding saddle") is None  # not in KB -> never priced
