"""Interactive WhatsApp-style test console for the Laundry Class agent.

Simulates one WhatsApp number talking to the agent, using the persistent
checkpointer so memory survives across runs (quit, rerun -> same memory).

Usage (from apps/whatsapp-agent):
    python scripts/lc_chat.py --phone +971500000101
    python scripts/lc_chat.py --phone +971555550101 --fresh   # in-memory, no persistence

Type a message and press enter. Commands: /state, /quit.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from laundry_class.runtime import InMemoryRuntime, PersistentRuntime  # noqa: E402


async def _loop(rt, phone: str) -> None:
    print(f"Laundry Class WhatsApp test console — you are {phone}")
    print("MOCK ENVIRONMENT · Live WhatsApp: Off · Live LLM: Off")
    print("Type a message. Commands: /state  /quit\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/state":
            state = await rt.get_state(phone)
            print("  [state]", {k: state.get(k) for k in
                   ("detected_intent", "current_order_id", "handoff_required",
                    "handoff_reason", "collected_order_details")})
            continue
        reply = await rt.process_message(phone, text)
        print(f"Agent: {reply.text}")
        if reply.handoff_required:
            print(f"  [handoff -> admin: {reply.handoff_reason}]")
        print()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone", default="+971500000101")
    ap.add_argument("--fresh", action="store_true", help="in-memory (no persistence)")
    args = ap.parse_args()

    if args.fresh:
        await _loop(InMemoryRuntime(), args.phone)
    else:
        async with PersistentRuntime() as rt:
            await _loop(rt, args.phone)


if __name__ == "__main__":
    asyncio.run(main())
