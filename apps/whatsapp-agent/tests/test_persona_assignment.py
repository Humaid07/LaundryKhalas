"""Persistent per-customer AI persona assignment (founder spec) — offline.

Covers the required guarantees:
  1. a new customer receives one APPROVED persona;
  2. the assignment is persisted;
  3. the same customer keeps the same persona across conversations/orders;
  4. backend/worker restarts do not change it;
  5. simultaneous first messages cannot assign two different personas;
  6. different customers can receive different personas;
  7. no unapproved persona name can be used;
  8. Claude cannot override the backend-assigned name;
  9. human takeover pauses the AI identity;
 10. releasing to AI restores the customer's original persona.
"""
from __future__ import annotations

import asyncio

from agents.whatsapp_agent.booking_tools import booking_system_prompt
from services import persona_assignment as pa

APPROVED = {"sara", "maya", "zoya", "hanna", "sofia", "max", "ben"}


class FakeCustomersRepo:
    """In-memory customers store with the SAME conditional-assign semantics as the DB
    (assign only when still unassigned) so concurrency behaviour is faithful."""

    def __init__(self, rows: dict):
        self.rows = rows                # id -> row dict
        self.writes = 0

    async def assign_ai_persona(self, customer_id, persona_id, persona_name, version):
        self.writes += 1
        await asyncio.sleep(0)          # yield, so a gather can interleave
        row = self.rows[customer_id]
        if not row.get("assigned_ai_persona_id"):     # conditional: first write wins
            row["assigned_ai_persona_id"] = persona_id
            row["assigned_ai_persona_name"] = persona_name
            row["ai_persona_assigned_at"] = "2026-07-29T00:00:00Z"
            row["ai_persona_assignment_version"] = version
        return dict(row)


def _customer(cid: str) -> dict:
    return {"id": cid}


# 1 + 2 -----------------------------------------------------------------------
async def test_new_customer_gets_one_approved_persona_and_it_persists():
    cust = _customer("cust-1")
    repo = FakeCustomersRepo({"cust-1": cust})
    persona = await pa.ensure_assigned(cust, repo)
    assert persona["id"] in APPROVED
    assert persona["name"] in {"Sara", "Maya", "Zoya", "Hanna", "Sofia", "Max", "Ben"}
    # Persisted on the record + mirrored onto the working dict.
    assert repo.rows["cust-1"]["assigned_ai_persona_id"] == persona["id"]
    assert cust["assigned_ai_persona_name"] == persona["name"]
    assert repo.rows["cust-1"]["ai_persona_assignment_version"] == pa.assignment_version()


# 3 + 4 -----------------------------------------------------------------------
async def test_same_customer_keeps_persona_across_conversations_and_restarts():
    cust = _customer("cust-2")
    repo = FakeCustomersRepo({"cust-2": cust})
    first = await pa.ensure_assigned(cust, repo)

    # New "conversation" (fresh dict from the persisted row) → same persona, no new write.
    reloaded = dict(repo.rows["cust-2"])
    again = await pa.ensure_assigned(reloaded, repo)
    assert again == first
    assert repo.writes == 1            # only the very first contact wrote

    # "Restart": deterministic selection for the same key yields the same persona even
    # before the persisted value is read.
    assert pa.select_for_key("cust-2") == first


# 5 --------------------------------------------------------------------------
async def test_simultaneous_first_messages_cannot_split_persona():
    cust = _customer("cust-3")
    repo = FakeCustomersRepo({"cust-3": cust})
    # Two racing first-message handlers, each with its own view of the (unassigned) row.
    view_a, view_b = dict(cust), dict(cust)
    a, b = await asyncio.gather(
        pa.ensure_assigned(view_a, repo), pa.ensure_assigned(view_b, repo))
    assert a == b                                   # identical persona
    assert repo.rows["cust-3"]["assigned_ai_persona_id"] == a["id"]


# 6 --------------------------------------------------------------------------
def test_different_customers_can_get_different_personas():
    picks = {pa.select_for_key(f"customer-{i}")["id"] for i in range(200)}
    assert len(picks) > 1                           # not everyone gets the same name
    assert picks <= APPROVED


# 7 --------------------------------------------------------------------------
def test_only_approved_names_are_ever_selectable():
    for i in range(500):
        assert pa.select_for_key(str(i))["id"] in APPROVED
    assert pa.is_approved("Sara") and pa.is_approved("ben")
    assert not pa.is_approved("Gandalf") and not pa.is_approved("")


def test_persisted_unapproved_name_is_ignored():
    # A stale/removed name must NOT be used — treated as unassigned.
    bad = {"id": "c", "assigned_ai_persona_id": "gandalf", "assigned_ai_persona_name": "Gandalf"}
    assert pa.persona_from_customer(bad) is None


# 8 --------------------------------------------------------------------------
def test_backend_assigned_name_drives_assistant_identity_and_prompt_forbids_override():
    cust = {"id": "c", "assigned_ai_persona_id": "maya", "assigned_ai_persona_name": "Maya"}
    ident = pa.assistant_identity(pa.persona_from_customer(cust))["assistant_identity"]
    assert ident["display_name"] == "Maya"
    assert ident["persona_type"] == "VIRTUAL_ASSISTANT"
    assert ident["organization"] == "Laundry Khalaas"
    # The stable prompt forbids Claude choosing/inventing a name.
    bp = booking_system_prompt().lower()
    assert "never select, change or invent your own name" in bp
    assert "assistant_identity.display_name" in booking_system_prompt()


# 9 + 10 ----------------------------------------------------------------------
def test_prompt_keeps_persona_paused_and_separate_during_human_takeover():
    bp = booking_system_prompt()
    assert "SEPARATE from the human Operations team" in bp
    assert "stay silent until it is handed back" in bp


async def test_release_to_ai_restores_the_same_persona():
    cust = _customer("cust-5")
    repo = FakeCustomersRepo({"cust-5": cust})
    original = await pa.ensure_assigned(cust, repo)
    # ... human takeover happens (AI paused) ... then the conversation is released.
    # The persona is read from the persisted record, so it is unchanged.
    after_release = dict(repo.rows["cust-5"])
    assert pa.persona_from_customer(after_release) == original
    assert await pa.ensure_assigned(after_release, repo) == original
    assert repo.writes == 1
