"""
Agent ablation study: for 3 representative (crop, query) pairs that
exactly match entries in the baseline matrix, re-run the full pipeline
with each specialist agent removed from the executor's registry, one
at a time. The full-agent baseline for each pair is NOT re-run here --
it's read back from evaluation/data/raw/ (same run_id), so the
comparison is apples-to-apples against data already collected.

Backs up TRUSTAI / continuous-learning state before this phase and
restores it after, so these deliberately-degraded runs don't
contaminate the main trust-evolution trajectory.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness_utils import (  # noqa: E402
    ABLATION_DIR, RAW_DIR, log_event, already_done, result_path,
    dump_json, to_jsonable, backup_state, restore_state, run_pipeline,
)

DEFAULT_LAT = 11.0168
DEFAULT_LON = 76.9558

# Must match run_ids in the baseline matrix exactly.
CASES = [
    {"baseline_run_id": "cotton_yield_r1", "crop": "cotton",
     "query": "What should I do to maximize cotton yield this season?"},
    {"baseline_run_id": "rice_suitability_r1", "crop": "rice",
     "query": "Is rice suitable to grow in this location right now, and what are the risks?"},
    {"baseline_run_id": "wheat_irrigation_r1", "crop": "wheat",
     "query": "Is it a good time to irrigate my wheat field?"},
]

AGENTS_TO_DROP = [
    "WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent",
]


def main():
    from app.orchestrator.executor import executor

    baseline_missing = [
        c["baseline_run_id"] for c in CASES
        if not already_done(RAW_DIR, c["baseline_run_id"])
    ]
    if baseline_missing:
        log_event({"phase": "agent_ablation", "run_id": "-", "status": "waiting_on_baseline",
                    "note": f"missing: {baseline_missing}"})
        print("Run run_baseline_matrix.py first (or at least these run_ids): ",
              baseline_missing)
        return

    backups = backup_state()
    log_event({"phase": "agent_ablation", "run_id": "-", "status": "state_backed_up"})

    try:
        for case in CASES:
            for dropped_agent in AGENTS_TO_DROP:
                run_id = f"ablation_{case['baseline_run_id']}_drop_{dropped_agent}"

                if already_done(ABLATION_DIR, run_id):
                    log_event({"phase": "agent_ablation", "run_id": run_id,
                                "status": "skipped_cached"})
                    continue

                log_event({"phase": "agent_ablation", "run_id": run_id,
                            "status": "started"})

                removed = executor.agent_registry.pop(dropped_agent, None)
                try:
                    result, elapsed, error = run_pipeline(
                        case["query"], case["crop"], DEFAULT_LAT, DEFAULT_LON
                    )
                finally:
                    if removed is not None:
                        executor.agent_registry[dropped_agent] = removed

                record = {
                    "run_id": run_id,
                    "baseline_run_id": case["baseline_run_id"],
                    "crop": case["crop"],
                    "query": case["query"],
                    "dropped_agent": dropped_agent,
                    "wall_time_seconds": round(elapsed, 3),
                    "error": error,
                    "result": result,
                }
                dump_json(to_jsonable(record), result_path(ABLATION_DIR, run_id))

                log_event({"phase": "agent_ablation", "run_id": run_id,
                            "status": "failed" if error else "completed",
                            "note": f"{round(elapsed, 1)}s"})
    finally:
        restore_state(backups)
        log_event({"phase": "agent_ablation", "run_id": "-", "status": "state_restored"})

    log_event({"phase": "agent_ablation", "run_id": "-", "status": "phase_complete"})


if __name__ == "__main__":
    main()
