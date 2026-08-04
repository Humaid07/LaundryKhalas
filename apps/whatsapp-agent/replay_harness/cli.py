"""Historical WhatsApp Replay Harness — command-line interface.

Commands:
  inspect-archive   Enumerate the archive + write parsing/inventory reports (no LLM).
  dry-run           Parse + estimate model calls / tokens / cost / runtime (no LLM).
  run               Replay conversations through the REAL agent (LIVE model calls).
  rerun             Re-run only conversations from a prior run at/above a severity.
  compare           Diff two prior runs turn-by-turn (metadata-level).

Safety: `run`/`rerun` install the capture-only transport and a fail-closed guard
BEFORE any pipeline import; the replay refuses to start unless the environment is
a verified test environment in capture-only mode.

Examples:
  python -m replay_harness inspect-archive
  python -m replay_harness dry-run --all
  python -m replay_harness run --sample 25 --seed 42
  python -m replay_harness run --all
  python -m replay_harness run --category alterations --limit 50
  python -m replay_harness rerun --run-id REPLAY_... --severity critical
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Optional

from .archive.loader import LoadResult, load_archives
from .core.config import ReplayConfig
from .core.models import Conversation


def _resolve_run_id(prefix: str = "REPLAY") -> str:
    # Date.now()-free deterministic-ish id from the process + a counter file is
    # overkill; use a short random token seeded by os.urandom (allowed here).
    import os

    return f"{prefix}_{os.urandom(4).hex().upper()}"


def _load(cfg: ReplayConfig) -> LoadResult:
    cfg.resolve_sources()
    if not cfg.resolved_primary_path:
        print("ERROR: primary archive not found.", file=sys.stderr)
        print("  Set WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH or place WhatsApp_All_Chats.zip", file=sys.stderr)
        print("  in ./test-data/whatsapp/ or your Downloads folder.", file=sys.stderr)
        sys.exit(2)
    print(f"Primary archive: {cfg.resolved_primary_path}")
    if cfg.resolved_fallback_path:
        print(f"Fallback archive: {cfg.resolved_fallback_path}")
    result = load_archives(cfg.resolved_primary_path, cfg.resolved_fallback_path)
    print(f"Parsed {len(result.conversations)} conversations · "
          f"{len(result.kept)} kept · {len(result.replayable)} replayable · "
          f"{len(result.duplicates)} duplicates excluded")
    return result


def _select(convs: list[Conversation], args) -> list[Conversation]:
    pool = list(convs)
    if getattr(args, "category", None):
        pool = [c for c in pool if c.category == args.category]
    if getattr(args, "conversation", None):
        pool = [c for c in pool if c.source_chat_id == args.conversation]
    if getattr(args, "with_images", False):
        pool = [c for c in pool if any(m.message_type.value == "image" for m in c.messages)]
    if getattr(args, "with_audio", False):
        pool = [c for c in pool if any(m.message_type.value == "audio" for m in c.messages)]
    if getattr(args, "sample", None):
        rnd = random.Random(getattr(args, "seed", None) or 0)
        pool = rnd.sample(pool, min(args.sample, len(pool)))
    if getattr(args, "limit", None):
        pool = pool[: args.limit]
    return pool


# --- commands --------------------------------------------------------------
def cmd_inspect_archive(args) -> int:
    cfg = ReplayConfig.from_env()
    result = _load(cfg)
    run_dir = Path(cfg.results_root) / "_archive_inspection"
    from .archive import inventory

    paths = inventory.write_all(result, run_dir)
    print("\nArchive reports written:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    return 0


def cmd_dry_run(args) -> int:
    cfg = ReplayConfig.from_env()
    result = _load(cfg)
    convs = _select(result.replayable, args) if not args.all else result.replayable
    from .report.estimate import estimate

    est = estimate(convs, concurrency=cfg.max_concurrency)
    print("\n=== DRY RUN ESTIMATE (no LLM calls) ===")
    for k, v in est.as_dict().items():
        print(f"  {k}: {v}")
    print(f"\n  model: {cfg.model}")
    print(f"  cost ceiling: ${cfg.max_cost_usd}")
    if cfg.max_cost_usd and est.estimated_cost_usd > cfg.max_cost_usd:
        print(f"  ⚠  ESTIMATE ${est.estimated_cost_usd:.2f} EXCEEDS CEILING ${cfg.max_cost_usd} — "
              f"the run will HARD-STOP at the ceiling unless WHATSAPP_REPLAY_ALLOW_EXCEED_COST=true.")
    return 0


def cmd_run(args) -> int:
    cfg = ReplayConfig.from_env()
    if getattr(args, "model", None):
        cfg.model = args.model
    if getattr(args, "max_cost", None) is not None:
        cfg.max_cost_usd = args.max_cost
    if getattr(args, "allow_exceed_cost", False):
        cfg.allow_exceed_cost_ceiling = True

    result = _load(cfg)
    convs = result.replayable if args.all else _select(result.replayable, args)
    if not args.all and not any([args.sample, args.category, args.conversation, args.limit,
                                 args.with_images, args.with_audio]):
        # Default first execution is a SAMPLE run unless --all is given.
        rnd = random.Random(args.seed or 0)
        convs = rnd.sample(convs, min(25, len(convs)))
        print("No selector given -> defaulting to a 25-conversation SAMPLE run "
              "(use --all for the full archive).")

    return asyncio.run(_execute(cfg, result, convs, run_id=args.run_id or _resolve_run_id(),
                                resume=args.resume))


def cmd_rerun(args) -> int:
    cfg = ReplayConfig.from_env()
    prior_dir = Path(cfg.results_root) / args.run_id
    summary = prior_dir / "replay_summary.csv"
    if not summary.is_file():
        print(f"ERROR: prior run summary not found: {summary}", file=sys.stderr)
        return 2
    sev_rank = {"critical": 1, "high": 2, "medium": 3, "low": 4}
    threshold = sev_rank.get((args.severity or "critical").lower(), 1)
    import csv

    target_ids = set()
    with summary.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["critical_failures"]) and threshold >= 1:
                target_ids.add(row["source_chat_id"])
            elif int(row["high_failures"]) and threshold >= 2:
                target_ids.add(row["source_chat_id"])
            elif int(row["medium_failures"]) and threshold >= 3:
                target_ids.add(row["source_chat_id"])
    result = _load(cfg)
    convs = [c for c in result.replayable if c.source_chat_id in target_ids]
    print(f"Re-running {len(convs)} conversations at/above severity '{args.severity}'.")
    new_run = _resolve_run_id("RERUN")
    return asyncio.run(_execute(cfg, result, convs, run_id=new_run, resume=False))


def cmd_compare(args) -> int:
    cfg = ReplayConfig.from_env()
    import csv

    def load_summary(run_id):
        p = Path(cfg.results_root) / run_id / "replay_summary.csv"
        rows = {}
        if p.is_file():
            with p.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    rows[r["source_chat_id"]] = r
        return rows

    base = load_summary(args.baseline)
    cand = load_summary(args.candidate)
    if not base or not cand:
        print("ERROR: one or both runs not found.", file=sys.stderr)
        return 2
    out = Path(cfg.results_root) / f"compare_{args.baseline}_vs_{args.candidate}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["chat_id", "baseline_result", "candidate_result",
                    "baseline_critical", "candidate_critical", "baseline_cost", "candidate_cost"])
        for cid in sorted(set(base) | set(cand)):
            b = base.get(cid, {}); c = cand.get(cid, {})
            w.writerow([cid, b.get("overall_result", "—"), c.get("overall_result", "—"),
                        b.get("critical_failures", ""), c.get("critical_failures", ""),
                        b.get("estimated_cost_usd", ""), c.get("estimated_cost_usd", "")])
    print(f"Comparison written: {out}")
    return 0


async def _execute(cfg: ReplayConfig, load_result: LoadResult, convs: list[Conversation],
                   *, run_id: str, resume: bool) -> int:
    from .runner import isolation, pipeline
    from .runner.replay_runner import run_replay
    from .report.generate import generate_all
    from .report.estimate import estimate

    if not convs:
        print("No conversations selected.", file=sys.stderr)
        return 1

    # Order for replay + assign synthetic identities.
    ordered = isolation.order_for_replay(convs, memory_mode=cfg.customer_memory_mode)
    identities = isolation.assign_identities(
        ordered, memory_mode=cfg.customer_memory_mode, run_id=run_id
    )
    synthetic_numbers = isolation.all_synthetic_numbers(identities.values())

    # Pre-run estimate + ceiling awareness.
    est = estimate(ordered, concurrency=cfg.max_concurrency)
    print(f"\nSelected {len(ordered)} conversations (~{est.turns} turns). "
          f"Estimated cost ${est.estimated_cost_usd:.2f} · ceiling ${cfg.max_cost_usd}.")
    if (cfg.max_cost_usd and est.estimated_cost_usd > cfg.max_cost_usd
            and not cfg.allow_exceed_cost_ceiling):
        print(f"  NOTE: estimate exceeds the ${cfg.max_cost_usd} ceiling; the run will "
              f"HARD-STOP when real spend reaches it.")

    # Bootstrap env (model override, allow-list, aggregation off) + reload settings.
    pipeline.bootstrap_env(cfg, synthetic_numbers)
    pipeline.install_all()

    # Fail-closed safety guard (installs + self-tests the capture transport).
    from .safety.guard import ReplaySafetyError, enforce

    try:
        await enforce(cfg)
    except ReplaySafetyError as exc:
        print("\n" + str(exc), file=sys.stderr)
        return 3
    print("Safety guard passed: capture-only transport verified, test environment confirmed.")

    # Clean prior synthetic replay state for a fresh run (unless resuming).
    if not resume:
        removed = await pipeline.cleanup_replay_state()
        if removed:
            print(f"Cleaned {removed} prior synthetic replay customers from the test DB.")

    run_dir = Path(cfg.results_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run id: {run_id}\nOutput: {run_dir}\n")

    done = {"n": 0}
    checkpoint_every = 25

    def _progress(res, all_results):
        done["n"] += 1
        flag = res.overall_result
        print(f"  [{done['n']}/{len(ordered)}] {res.source_chat_id} -> {flag} "
              f"({len(res.turns)} turns, ${res.usage_total.estimated_cost_usd:.4f})")
        # Periodic report checkpoint so a mid-run interruption still leaves a
        # complete, openable report set for everything completed so far.
        if done["n"] % checkpoint_every == 0:
            try:
                by_id = {r.source_chat_id: r for r in all_results}
                ordered_so_far = [by_id[c.source_chat_id] for c in ordered
                                  if c.source_chat_id in by_id]
                generate_all(ordered_so_far, load_result, run_dir, cfg)
                print(f"    · checkpoint: reports written for {len(ordered_so_far)} conversations")
            except Exception as exc:  # noqa: BLE001 - checkpoint must never kill the run
                print(f"    · checkpoint skipped ({exc})")

    outcome = await run_replay(ordered, identities, cfg, run_id, run_dir,
                               resume=resume, on_result=_progress)

    # Order results to match input order for stable reports.
    by_id = {r.source_chat_id: r for r in outcome.results}
    ordered_results = [by_id[c.source_chat_id] for c in ordered if c.source_chat_id in by_id]

    paths = generate_all(ordered_results, load_result, run_dir, cfg)
    print("\n=== RUN COMPLETE ===")
    print(f"  conversations replayed: {len(ordered_results)}")
    print(f"  total real cost: ${outcome.total_cost:.4f} (ceiling ${cfg.max_cost_usd})")
    if outcome.stopped_for_cost:
        print(f"  ⚠  STOPPED AT COST CEILING (${cfg.max_cost_usd}). Re-run with "
              f"--allow-exceed-cost or a higher --max-cost to continue.")
    print(f"  failed exports: {paths.get('_failed_counts')}")
    print("\n  Download locations:")
    for k in ("replay_report.html", "replay_summary.csv", "replay_turns.csv",
              "replay_conversations.jsonl", "critical_failures.csv",
              "replay_cost_summary.json"):
        print(f"    {k}: {paths.get(k)}")
    print(f"    (all outputs under: {run_dir})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="replay_harness", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect-archive", help="Enumerate archive + write reports (no LLM)")

    dr = sub.add_parser("dry-run", help="Estimate cost/tokens/runtime (no LLM)")
    dr.add_argument("--all", action="store_true")
    _add_selectors(dr)

    r = sub.add_parser("run", help="Replay through the REAL agent (LIVE model calls)")
    r.add_argument("--all", action="store_true", help="Replay the full archive")
    r.add_argument("--run-id", default=None)
    r.add_argument("--resume", action="store_true")
    r.add_argument("--model", default=None, help="Override replay model id")
    r.add_argument("--max-cost", type=float, default=None, help="Cost ceiling USD")
    r.add_argument("--allow-exceed-cost", action="store_true")
    _add_selectors(r)

    rr = sub.add_parser("rerun", help="Re-run failed conversations from a prior run")
    rr.add_argument("--run-id", required=True)
    rr.add_argument("--severity", default="critical", choices=["critical", "high", "medium"])

    cmp = sub.add_parser("compare", help="Diff two prior runs")
    cmp.add_argument("--baseline", required=True)
    cmp.add_argument("--candidate", required=True)
    return p


def _add_selectors(sp):
    sp.add_argument("--category", default=None)
    sp.add_argument("--conversation", default=None, help="A single source_chat_id")
    sp.add_argument("--sample", type=int, default=None)
    sp.add_argument("--seed", type=int, default=None)
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--with-images", action="store_true")
    sp.add_argument("--with-audio", action="store_true")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return {
        "inspect-archive": cmd_inspect_archive,
        "dry-run": cmd_dry_run,
        "run": cmd_run,
        "rerun": cmd_rerun,
        "compare": cmd_compare,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
