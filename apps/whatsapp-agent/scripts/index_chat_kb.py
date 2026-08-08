"""Index the real WhatsApp chat archive into the redacted retrieval KB (Phase 2).

Parses `chats_html.zip` (one HTML per contact, stable WhatsApp-export markup),
PII-REDACTS every message (services.sanitize: phones/emails), groups messages into
overlapping exchange chunks, embeds them locally with fastembed (bge-small-en-v1.5),
and upserts into `chat_knowledge_base` (migration 000051). Re-runnable: dedupe_key
makes it idempotent.

NO raw PII is written — the contact number is only ever a salted hash (`source_ref`);
message bodies are sanitized before embedding/storage.

Usage (from apps/whatsapp-agent, with the venv, DATABASE_MODE=supabase):
    python scripts/index_chat_kb.py "C:\\path\\to\\chats_html.zip"
    python scripts/index_chat_kb.py "...zip" --limit 20        # index first 20 chats (smoke test)
"""
from __future__ import annotations

import asyncio
import hashlib
import html as _html
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from services import chat_kb  # noqa: E402
from services.sanitize import sanitize_text, scrub_conversational_names  # noqa: E402
from settings import get_settings  # noqa: E402

# Stable WhatsApp-export markup (see replay_harness/archive/html_parser.py).
_MSG_RE = re.compile(
    r'class="[^"]*__message-(in|out)[^"]*".*?'
    r'<span dir="[^"]*" class="__selectable-text[^"]*">(.*?)</span>',
    re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")

CHUNK_SIZE = 8       # messages per chunk
CHUNK_OVERLAP = 2    # overlap so an exchange spanning a boundary is still retrievable
BATCH = 256          # embed/insert batch size


def _clean(text: str) -> str:
    text = text.replace("<br>", "\n").replace("<br/>", "\n")
    text = _TAG.sub("", text)
    return _html.unescape(text).strip()


def _market_for(contact: str) -> str:
    digits = re.sub(r"\D", "", contact)
    return "QA" if digits.startswith("974") else "AE"


def _contact_name_tokens(contact: str) -> list[str]:
    """Likely saved-contact name tokens from the export folder label. If the label
    is a phone number it yields nothing (sanitize_text already masks numbers)."""
    label = re.sub(r"[+_\-.]", " ", contact)
    return [t for t in label.split() if t.isalpha() and len(t) >= 2]


def parse_chat(raw: str, contact: str = "") -> list[tuple[str, str]]:
    """Return [(role, text)] where role is 'Customer' or 'Agent', PII already redacted.

    Redaction order per message: structural PII (phones/emails/URLs/addresses via
    sanitize_text) → the saved contact display name (if any) → intro-phrase names.
    """
    name_tokens = _contact_name_tokens(contact)
    out: list[tuple[str, str]] = []
    for direction, body in _MSG_RE.findall(raw):
        txt = _clean(body)
        if not txt:
            continue
        redacted = sanitize_text(txt, mask_names=bool(name_tokens), names=name_tokens) or ""
        redacted = scrub_conversational_names(redacted)
        if not redacted.strip():
            continue
        role = "Customer" if direction == "in" else "Agent"
        out.append((role, redacted))
    return out


def chunk_messages(msgs: list[tuple[str, str]]) -> list[str]:
    """Overlapping windows rendered as 'Role: text' lines."""
    chunks: list[str] = []
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    for i in range(0, len(msgs), step):
        window = msgs[i:i + CHUNK_SIZE]
        if not window:
            break
        text = "\n".join(f"{role}: {text}" for role, text in window).strip()
        if len(text) >= 20:            # skip trivially tiny windows
            chunks.append(text)
        if i + CHUNK_SIZE >= len(msgs):
            break
    return chunks


async def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print("Usage: python scripts/index_chat_kb.py <chats_html.zip> [--limit N]")
        return 2
    zip_path = args[0]
    limit = None
    for a in argv:
        if a.startswith("--limit"):
            limit = int(a.split("=", 1)[1]) if "=" in a else int(argv[argv.index(a) + 1])

    s = get_settings()
    if getattr(s, "database_mode", None) != "supabase":
        print("Refusing: DATABASE_MODE must be 'supabase' (the KB lives in pgvector).")
        return 1

    z = zipfile.ZipFile(zip_path)
    html_files = [n for n in z.namelist() if n.endswith(".html")]
    if limit:
        html_files = html_files[:limit]
    print(f"chats: {len(html_files)}  (embedding model: {chat_kb.MODEL_NAME})")

    # Build (source_ref, chunk_index, market, content, dedupe_key) rows.
    rows: list[tuple] = []
    for n in html_files:
        contact = n.split("/")[0]
        raw = z.read(n).decode("utf-8", "ignore")
        msgs = parse_chat(raw, contact)
        if not msgs:
            continue
        market = _market_for(contact)
        source_ref = "chat-" + hashlib.sha1(contact.encode()).hexdigest()[:12]
        for idx, content in enumerate(chunk_messages(msgs)):
            dedupe = hashlib.sha1(f"{source_ref}|{idx}".encode()).hexdigest()
            rows.append((source_ref, idx, market, content, dedupe))
    # Resumable: skip chunks already stored so a re-run only embeds the remainder
    # (embedding is the slow step). Idempotent inserts already prevent duplicates;
    # this just avoids re-embedding thousands of already-indexed chunks.
    try:
        existing = {
            r["dedupe_key"]
            for r in await database.fetch("select dedupe_key from chat_knowledge_base")
        }
    except Exception:  # noqa: BLE001 — empty/absent table → nothing to skip
        existing = set()
    total_built = len(rows)
    rows = [r for r in rows if r[4] not in existing]
    print(f"chunks to index: {len(rows)}  (built {total_built}, already present {total_built - len(rows)})")
    if not rows:
        print("nothing new to index; ensuring HNSW index exists…", flush=True)

    # One INSERT per batch via unnest — a single round-trip instead of 256 sequential
    # ones (the DB is remote; per-row round-trips dominated wall-clock otherwise).
    _INSERT = (
        "insert into chat_knowledge_base "
        "(source_ref, chunk_index, market, content, embedding, token_estimate, dedupe_key) "
        "select s, ci, m, c, e::vector, t, d "
        "from unnest($1::text[],$2::int[],$3::text[],$4::text[],$5::text[],$6::int[],$7::text[]) "
        "as u(s, ci, m, c, e, t, d) "
        "on conflict (dedupe_key) do nothing"
    )
    inserted = 0

    async def _run(sql: str, *params, timeout: float) -> str:
        # Bulk-load pattern: inserting into a live HNSW index costs a graph update
        # per row, so we drop the ANN index, bulk-insert, then rebuild it ONCE.
        #
        # CRITICAL: never hold a DB connection across the (multi-second) embedding
        # step. The Supabase pooler silently drops an idle connection, and asyncpg —
        # with no command_timeout — then blocks FOREVER on the next execute over the
        # dead socket. So each DB op takes a fresh, short-lived connection with a hard
        # per-call timeout, and retries on a fresh pool if the socket went stale.
        # Every statement is idempotent (dedupe_key / create-if-not-exists), so a
        # retry can never double-insert.
        last: Exception | None = None
        for attempt in range(4):
            try:
                p = await database.get_pool()
                async with p.acquire() as c:
                    return await c.execute(sql, *params, timeout=timeout)
            except Exception as e:  # noqa: BLE001 — reconnect + retry on any DB/socket error
                last = e
                print(f"    retry {attempt + 1}/4 after {type(e).__name__}: {e}", flush=True)
                await database.close_pool()  # force a fresh physical connection next acquire
        raise last  # type: ignore[misc]

    await _run("drop index if exists idx_chat_kb_embedding", timeout=120)
    try:
        for start in range(0, len(rows), BATCH):
            batch = rows[start:start + BATCH]
            vecs = chat_kb.embed_texts([r[3] for r in batch])  # no DB connection held here
            res = await _run(
                _INSERT,
                [r[0] for r in batch], [int(r[1]) for r in batch], [r[2] for r in batch],
                [r[3] for r in batch], [chat_kb.vector_literal(v) for v in vecs],
                [max(1, len(r[3]) // 4) for r in batch], [r[4] for r in batch],
                timeout=90,
            )
            try:
                inserted += int(res.rsplit(" ", 1)[1])  # "INSERT 0 <n>"
            except (ValueError, IndexError):
                pass
            print(f"  embedded+upserted {min(start + BATCH, len(rows))}/{len(rows)}  (new: {inserted})", flush=True)
    finally:
        # Always restore the ANN index, so a mid-run stop still leaves the table
        # queryable (seq scan) and this rebuild (or the migration) restores the index.
        print("rebuilding HNSW index…", flush=True)
        await _run(
            "create index if not exists idx_chat_kb_embedding "
            "on chat_knowledge_base using hnsw (embedding vector_cosine_ops)",
            timeout=600,
        )

    total = await database.fetchval("select count(*) from chat_knowledge_base")
    print(f"done. inserted {inserted} new; table now holds {total} chunks.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
