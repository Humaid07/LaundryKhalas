"""Shared advanced routing engine (ONE engine for test + production orders).

Pure, environment-agnostic evaluation (eligibility -> availability -> slots ->
ranking -> explanation) plus thin adapters that load TEST xor PRODUCTION records.
See docs/superpowers/specs/2026-08-06-advanced-routing-engine-design.md.
"""
