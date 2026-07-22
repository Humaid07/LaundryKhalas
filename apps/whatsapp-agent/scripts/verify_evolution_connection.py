"""Verify that the Evolution API is reachable from FastAPI (read-only).

Usage (from apps/whatsapp-agent, with .env configured):
    python scripts/verify_evolution_connection.py

Reports the resolved Evolution config (base URL, instance, whether the API key is
loaded — never the key itself, and never a live-provider requirement), then calls
the read-only Evolution endpoint GET {base}/instance/connectionState/{instance}
and prints the connection state. Never sends a message. Never prints secrets.
Exits non-zero on failure so it is CI-friendly.

Note: this checks reachability using the EVOLUTION_* config directly, regardless
of WHATSAPP_MODE. WHATSAPP_MODE only decides whether the running app actually
routes live traffic to Evolution — it is reported here but does not gate the check.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from channels.evolution_whatsapp import EvolutionWhatsAppChannel  # noqa: E402
from settings import get_settings  # noqa: E402


async def main() -> int:
    s = get_settings()
    key_loaded = bool(s.evolution_api_key)

    print("LaundryKhalas — Evolution API connection check")
    print(f"  WHATSAPP_MODE            = {s.whatsapp_mode}")
    print(f"  EVOLUTION_API_BASE_URL   = {s.evolution_api_base_url or '(blank)'}")
    print(f"  EVOLUTION_INSTANCE_NAME  = {s.evolution_instance_name or '(blank)'}")
    print(f"  EVOLUTION_API_KEY        = {'loaded' if key_loaded else 'MISSING'}")
    print(f"  evolution_live_ready     = {s.evolution_live_ready}")

    if s.whatsapp_mode.lower() != "evolution":
        print(
            f"\n[NOTE] WHATSAPP_MODE is '{s.whatsapp_mode}', not 'evolution'. The app will "
            "NOT route live WhatsApp traffic to Evolution until WHATSAPP_MODE=evolution. "
            "Still checking raw reachability below."
        )

    # Config completeness (do not attempt a request against a blank base/instance).
    missing = [
        name
        for name, val in (
            ("EVOLUTION_API_BASE_URL", s.evolution_api_base_url),
            ("EVOLUTION_API_KEY", s.evolution_api_key),
            ("EVOLUTION_INSTANCE_NAME", s.evolution_instance_name),
        )
        if not val
    ]
    if missing:
        print(f"\n[FAIL] Missing Evolution config: {', '.join(missing)}.")
        return 1

    channel = EvolutionWhatsAppChannel.from_settings()
    print(
        f"\n  GET {s.evolution_api_base_url.rstrip('/')}"
        f"/instance/connectionState/{s.evolution_instance_name}"
    )
    try:
        state = await channel.instance_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        print(f"\n[FAIL] Evolution returned HTTP {code}.")
        if code in (401, 403):
            print("       -> API key rejected. Check EVOLUTION_API_KEY.")
        elif code == 404:
            print(
                f"       -> Instance '{s.evolution_instance_name}' not found. "
                "Check EVOLUTION_INSTANCE_NAME (is the instance created in Evolution?)."
            )
        return 1
    except (httpx.ConnectError, httpx.ConnectTimeout):
        print(
            f"\n[FAIL] Could not reach Evolution at {s.evolution_api_base_url}. "
            "Is the Evolution server running and the URL correct?"
        )
        return 1
    except httpx.HTTPError as exc:  # noqa: BLE001 - report transport errors generically
        print(f"\n[FAIL] Evolution request failed: {type(exc).__name__}: {exc}")
        return 1

    # Evolution shapes this as {"instance": {"instanceName": ..., "state": "open"}}
    # or a flat {"state": "open"} depending on version.
    inner = state.get("instance") if isinstance(state, dict) else None
    conn_state = ""
    if isinstance(inner, dict):
        conn_state = inner.get("state", "")
    if not conn_state and isinstance(state, dict):
        conn_state = state.get("state", "")

    print(f"\n  connection state: {conn_state or '(unknown shape)'}")
    print(f"  raw response    : {state}")

    if conn_state == "open":
        print("\n[OK] Evolution reachable and the instance is CONNECTED (state=open).")
        return 0
    if conn_state in ("connecting", "close"):
        print(
            f"\n[WARN] Evolution is reachable but the instance state is '{conn_state}'. "
            "It is not connected to WhatsApp — scan the QR / pair the instance in Evolution."
        )
        return 0
    print("\n[OK] Evolution reachable (state shape unrecognised — see raw response above).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
