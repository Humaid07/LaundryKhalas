# ADR: Project Documentation and Memory Rule

## Status

Accepted — in force from 2026-07-18.

## Context

Work on LaundryKhalas spans many Claude Code sessions, over weeks, with no
persistent memory between them beyond what's written to disk in this repo.
Previous tasks (WhatsApp Operations Agent backend, then the Admin UI)
produced good documentation (audit reports, architecture docs, decision
docs), but there was no single rulebook a new session could read first to
recover full context, and no standing requirement that every task leave
behind a report usable for weekly updates, founder presentations, or
technical handover.

Without an enforced rule, documentation quality depends on whether that
session's task happened to prompt it. That's not reliable enough for a
project intended to run across many sessions and eventually be
demoed/reported on weekly.

## Decision

1. A repo-root `CLAUDE.md` is the permanent operating rulebook and memory
   for every Claude Code session in this repository. It must be read and
   followed at the start of every task. It is updated carefully over time,
   not replaced wholesale.

2. Every major task must produce a build report at
   `docs/build-reports/YYYY-MM-DD-task-name.md`, covering: objective, what
   was built and why, files created/modified, API/DB/UI/agent/integration
   changes, what is mock-only vs. live vs. deferred, tests run and their
   results, bugs/limitations, security/privacy notes, and the next
   recommended step.

3. Every major task must also update `docs/weekly-reports/week-XX-report.md`
   (executive summary, what shipped, progress by area, blockers, risks,
   decisions needed, deviations from roadmap, next week's plan) and
   `docs/presentation-notes/week-XX-presentation-notes.md` (demo flow,
   screenshots needed, talking points, business value, honest caveats).

4. `docs/00-Home.md` is the Obsidian-style entry point and must be updated
   after every major task to link the latest build report, weekly report,
   presentation notes, and any new/changed architecture or decision docs.

5. A task is not considered complete until this documentation is updated.
   The end-of-task summary must honestly report what is done, what is
   mock-only, what is deferred, and what tests actually ran — never claim
   completion or passing tests that didn't happen.

## Consequences

- Slightly more overhead per task (report-writing time), in exchange for
  every session being able to reconstruct full project state from
  `CLAUDE.md` + `docs/00-Home.md` alone, without needing prior chat
  history.
- Founder/team updates and presentation prep become a byproduct of normal
  work instead of a separate scramble.
- Documentation produced before this ADR (e.g.
  `docs/audits/admin-ui-start-report.md`,
  `docs/decisions/admin-ui-design-decisions.md`) is not retroactively
  reformatted into build-report shape; it remains valid as-is and is
  linked from `docs/00-Home.md`. Only tasks from this point forward follow
  the full build-report / weekly-report / presentation-notes structure.

## Related

- [[CLAUDE|CLAUDE.md]] (repo root) — full rulebook this ADR supports.
- [[00-Home]] — where the latest reports are linked from.
