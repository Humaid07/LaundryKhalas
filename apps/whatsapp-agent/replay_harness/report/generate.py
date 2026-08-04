"""Write the full downloadable report set for a run."""
from __future__ import annotations

from pathlib import Path

from ..archive import inventory as inv_writer
from ..archive.loader import LoadResult
from ..core.config import ReplayConfig
from ..core.models import ReplayConversationResult
from . import writers
from .html_report import write_html_report


def generate_all(
    results: list[ReplayConversationResult],
    load_result: LoadResult,
    run_dir: Path,
    cfg: ReplayConfig,
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # Archive/parsing reports.
    paths.update({k: Path(v) for k, v in inv_writer.write_all(load_result, run_dir).items()})

    # Result reports.
    writers.write_summary_csv(results, run_dir / "replay_summary.csv", cfg)
    writers.write_turns_csv(results, run_dir / "replay_turns.csv", cfg)
    writers.write_conversations_jsonl(results, run_dir / "replay_conversations.jsonl", cfg)
    writers.write_turns_jsonl(results, run_dir / "replay_turns.jsonl", cfg)
    writers.write_critical_failures_csv(results, run_dir / "critical_failures.csv", cfg)
    writers.write_cost_reports(
        results, run_dir / "replay_cost_report.csv", run_dir / "replay_cost_summary.json", cfg
    )
    failed_counts = writers.write_failed_exports(results, run_dir, cfg)
    write_html_report(results, run_dir / "replay_report.html", cfg)

    for name in (
        "replay_summary.csv", "replay_turns.csv", "replay_conversations.jsonl",
        "replay_turns.jsonl", "critical_failures.csv", "replay_cost_report.csv",
        "replay_cost_summary.json", "replay_report.html",
    ):
        paths[name] = run_dir / name
    paths["failed_conversations/"] = run_dir / "failed_conversations"
    return {k: str(v) for k, v in paths.items()} | {"_failed_counts": str(failed_counts)}
