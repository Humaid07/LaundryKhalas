"""Run all 10 Laundry Class test cases (+ isolation + restart) and print a clean
transcript. Used to capture evidence for whatsapp_agent_test_report.md.

    python scripts/lc_run_testcases.py > ../../docs/build-reports/lc-transcripts.txt
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from laundry_class import observability as obs  # noqa: E402
from laundry_class.runtime import InMemoryRuntime, PersistentRuntime  # noqa: E402

_INBOX = []
obs.set_admin_sink(_INBOX.append)


async def convo(rt, phone, title, msgs):
    print(f"\n===== {title}  (thread whatsapp:{phone}) =====")
    for m in msgs:
        r = await rt.process_message(phone, m)
        print(f"Customer: {m}")
        print(f"Agent:    {r.text}")
        if r.handoff_required:
            print(f"          [HANDOFF -> admin | reason: {r.handoff_reason}]")


async def main():
    rt = InMemoryRuntime()
    await convo(rt, "+971555550101", "TC1 Price enquiry + follow-up memory",
                ["Hi, how much is dry cleaning for a suit?", "And a shirt?",
                 "What would the total be for one suit and three shirts?"])
    await convo(rt, "+971555550102", "TC2 New order over multiple messages",
                ["I want to arrange a laundry pickup.", "My name is Maya and I am in JLT.",
                 "I need wash and iron for five shirts and two trousers.", "Pickup tomorrow evening.",
                 "7 pm. Same number. Address is Cluster X, Tower 2, Apartment 804.", "Cash.",
                 "Yes, confirm.", "What time did I choose?"])
    await convo(rt, "+971500000101", "TC3 Existing order status",
                ["Hi, where is my order?", "What did I send?", "How much do I need to pay?"])
    await convo(rt, "+971500000102", "TC4 Delivery reschedule",
                ["I got a message saying my delivery is coming around 4. I won't be home.",
                 "Please come at 6 pm.", "Which address will they come to?"])
    await convo(rt, "+971500000103", "TC5 Refund request",
                ["I am not happy with my last order. I want a refund.",
                 "Some of the clothes still smell dirty.", "So is my refund approved?"])
    await convo(rt, "+971500000104", "TC6 Damaged garment complaint",
                ["My silk dress has a tear after cleaning.",
                 "The order number is LC-TEST-1004. It was delivered today.",
                 "Will you pay for the dress?"])
    await convo(rt, "+971555550107", "TC7 Unknown item / hallucination prevention",
                ["How much do you charge to clean a horse-riding saddle?",
                 "Just give me an estimate.", "Can you collect it today?"])
    # TC8
    await convo(rt, "+971555550801", "TC8 Phone A",
                ["My name is Daniel. I need five shirts collected from Apartment 304, "
                 "Marina Heights, Dubai Marina, tomorrow at 11 am.", "What address did I give you?"])
    await convo(rt, "+971555550802", "TC8 Phone B (isolation)",
                ["Hi, what address do you have for me?", "What is Daniel's order?"])
    await convo(rt, "+971555550801", "TC8 Phone A return", ["What time is my pickup?"])
    await convo(rt, "+971555550909", "TC9 Natural multi-turn",
                ["I have two dresses.", "Dry cleaning.",
                 "One is a normal dress and one is an evening gown.", "How much?", "Express?",
                 "Yes.", "Pickup from Downtown.", "Tomorrow morning.", "10.", "Card."])
    await convo(rt, "+971555550110", "TC10 Explicit human support + payment dispute",
                ["I need to speak to a real person.", "I was charged twice."])

    # Part 8 restart
    with tempfile.TemporaryDirectory() as d:
        db = str(Path(d) / "restart.sqlite")
        async with PersistentRuntime(db) as p1:
            for m in ["I want to arrange a pickup.", "My name is Omar and I am in Deira.",
                      "Wash and fold, one 6kg bag.", "Tomorrow at 5 pm."]:
                await p1.process_message("+971555551234", m)
        print("\n===== Part 8 Application restart (persistent memory) =====")
        print("[application stopped and restarted — new process, same SQLite checkpointer]")
        async with PersistentRuntime(db) as p2:
            r = await p2.process_message("+971555551234", "What pickup time did I request?")
            print("Customer: What pickup time did I request?")
            print(f"Agent:    {r.text}")

    print("\n\n===== Sample administrator notifications captured =====")
    for n in _INBOX[:2]:
        print("-" * 50)
        print(n)


if __name__ == "__main__":
    asyncio.run(main())
