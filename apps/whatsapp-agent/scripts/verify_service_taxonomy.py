"""CLI: verify the service taxonomy is consistent across all surfaces.

Compares the backend canonical catalog against the WhatsApp agent options, the
SEO agent taxonomy and the dashboard TS mirror. Prints a human-readable report
and exits non-zero if anything drifts — safe to wire into CI.

Run from apps/whatsapp-agent:

    python -m scripts.verify_service_taxonomy
    python scripts/verify_service_taxonomy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a bare script (python scripts/verify_service_taxonomy.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.taxonomy_sync import check_taxonomy_sync  # noqa: E402


def main() -> int:
    report = check_taxonomy_sync()
    surfaces = report["surfaces"]

    print("LaundryKhalas — service taxonomy sync check")
    print("=" * 52)
    print(f"backend   ({len(surfaces['backend'])}): {surfaces['backend']}")
    print(f"whatsapp  ({len(surfaces['whatsapp'])}): {surfaces['whatsapp']}")
    print(f"seo       ({len(surfaces['seo'])}): {surfaces['seo']}")
    print(f"dashboard ({len(surfaces['dashboard'])}): {surfaces['dashboard']}")
    print("-" * 52)

    if report["in_sync"]:
        print("OK — all surfaces are in sync.")
        return 0

    print("MISMATCH — Service taxonomy mismatch detected:")
    for m in report["mismatches"]:
        print(f"  [{m['surface']}] {m['detail']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
