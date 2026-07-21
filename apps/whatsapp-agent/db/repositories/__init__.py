"""Supabase-backed repositories (DATABASE_MODE=supabase).

Each module exposes async functions that read/write the dev/test Supabase
schema via ``db.database`` helpers. All rows returned are plain dicts. These are
used by the FastAPI conversation/order/flag endpoints when running against
Supabase; the SQLite local mode uses the existing ``services.*`` stores instead.
"""
