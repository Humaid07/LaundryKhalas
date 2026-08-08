"""Redacted past-conversation retrieval KB (Phase 2 of knowledge reinforcement).

The agent grounds replies in real precedent from past customer chats WITHOUT ever
seeing raw PII: chats are parsed, PII-redacted (services.sanitize), chunked and
embedded locally with fastembed (BAAI/bge-small-en-v1.5, 384-dim), and stored in
Supabase pgvector (`chat_knowledge_base`, migration 000051). At query time the
agent's `search_past_conversations` tool embeds its query here and does a cosine
lookup.

Design rules:
- LOCAL embeddings only (no external vendor); model is lazy-loaded once.
- FAIL SOFT: any error, missing model, non-Supabase mode, or empty table returns
  [] — retrieval must never break a customer turn.
- Rows are already redacted; nothing here re-introduces PII.
"""
from __future__ import annotations

import functools

from db import database

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
# Small on-CPU embedding batch. fastembed truncates to bge-small's 512-token max and
# pads every sequence in a batch to the batch's longest, so a wide default batch (256)
# on real long chats builds a huge (256, 512) tensor that takes MINUTES per call —
# indexing appeared to "hang". 16 keeps each onnx inference small and steady
# (~40s per 256 texts vs several minutes), with no effect on the vectors produced.
EMBED_BATCH = 16


@functools.lru_cache(maxsize=1)
def _embedder():
    # Imported lazily so the heavy onnxruntime dependency loads only when the KB is
    # actually used (indexing or the first retrieval), never at app import time.
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: list[str], batch_size: int = EMBED_BATCH) -> list[list[float]]:
    """Embed a batch of texts to 384-dim cosine-normalised vectors."""
    return [
        [float(x) for x in vec]
        for vec in _embedder().embed(list(texts), batch_size=batch_size)
    ]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def vector_literal(vec: list[float]) -> str:
    """pgvector text literal: '[0.1,0.2,...]' — asyncpg casts it via ::vector."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


async def search(
    query: str, *, market: str = "AE", k: int = 4, min_score: float = 0.30
) -> list[dict]:
    """Return up to `k` redacted precedent snippets most similar to `query`.

    Cosine similarity (1 - pgvector distance); only snippets at/above `min_score`.
    Never raises — returns [] on any problem.
    """
    if not (query or "").strip() or not database.is_supabase_mode():
        return []
    try:
        vec = embed_query(query)
    except Exception:  # noqa: BLE001 — model load / embed failure must not break a turn
        return []
    lit = vector_literal(vec)
    try:
        rows = await database.fetch(
            "select source_ref, content, chunk_index, "
            "1 - (embedding <=> $1::vector) as score "
            "from chat_knowledge_base where market = $2 "
            "order by embedding <=> $1::vector limit $3",
            lit, market, int(k),
        )
    except Exception:  # noqa: BLE001 — table absent / DB error → no precedent
        return []
    out = [
        {"source_ref": r["source_ref"], "content": r["content"],
         "chunk_index": r["chunk_index"], "score": round(float(r["score"]), 4)}
        for r in rows
    ]
    return [r for r in out if r["score"] >= min_score]
