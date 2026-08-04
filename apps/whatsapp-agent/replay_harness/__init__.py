"""Historical WhatsApp Replay Harness.

Replays original inbound customer messages from an exported WhatsApp archive
through the CURRENT LaundryKhalas WhatsApp agent pipeline, captures the new
replies / tool calls / workflow state / cost, evaluates them against current
rules, and produces downloadable reports.

The harness NEVER contacts real customers: the outbound Evolution transport is
replaced by a capture-only channel and a fail-closed safety guard aborts unless
the environment is a verified test environment in capture-only mode.

See docs/superpowers/specs/2026-08-04-whatsapp-historical-replay-harness-design.md
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
