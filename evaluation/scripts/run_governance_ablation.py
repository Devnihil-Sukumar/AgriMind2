"""
TRUSTAI governance ablation: same 3 representative (crop, query) pairs
as the agent-ablation study, re-run with the pre-execution governance
gate forced to never reject an agent (the Bayesian trust/risk math
still runs and is recorded -- only the "reject" branch that would
skip an agent's execution is disabled). Compares against the same
baseline run_ids used by the agent-ablation study.

Backs up / restores TRUSTAI + continuous-learning state around this
phase for the same reason as the agent-ablation script.
"""

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness_utils import (  # noqa: E402
    GOVERNANCE_DIR, RAW_DIR, log_event, already_done, result_path,
    dump_json, to_jsonable, backup_state, restore_state, run_pipeline,
)

DEFAULT_LAT = 11.0168
DEFAULT_LON = 76.9558

CASES = [
    {"baseline_run_id": "cotton_yield_r1", "crop": "cotton",
     "query": "What should I do to maximize cotton yield this season?"},
    {"baseline_run_id": "rice_suitability_r1", "crop": "rice",
     "query": "Is rice suitable to grow in this location right now, and what are the risks?"},
    {"baseline_run_id": "wheat_irrigation_r1", "crop": "wheat",
     "query": "Is it a good time to irrigate my wheat field?"},
]


def main():
    from app.governance.trustai import trustai

    original_review = trustai.review

    def review_never_reject(agent_name):
        record = original_review(agent_name)
        if record.decision.action == "reject":
            forced_decision = dataclasses.replace(
                record.decision,
                action="auto_execute",
                rationale=record.decision.rationale
                + " [EVAL: governance-ablation override, would have been rejected]",
            )
            record = dataclasses.replace(record, decision=forced_decision)
        return record

    baseline_missing = [
        c["baseline_run_id"] for c in CASES
        if not already_done(RAW_DIR, c["baseline_run_id"])
    ]
    if baseline_missing:
        log_event({"phase": "governance_ablation", "run_id": "-", "status": "waiting_on_baseline",
                    "note": f"missing: {baseline_missing}"})
        print("Run run_baseline_matrix.py first (or at least these run_ids): ",
              baseline_missing)
        return

    backups = backup_state()
    log_event({"phase": "governance_ablation", "run_id": "-", "status": "state_backed_up"})

    try:
        trustai.review = review_never_reject
        try:
            for case in CASES:
                run_id = f"governance_off_{case['baseline_run_id']}"

                if already_done(GOVERNANCE_DIR, run_id):
                    log_event({"phase": "governance_ablation", "run_id": run_id,
                                "status": "skipped_cached"})
                    continue

                log_event({"phase": "governance_ablation", "run_id": run_id,
                            "status": "started"})

                result, elapsed, error = run_pipeline(
                    case["query"], case["crop"], DEFAULT_LAT, DEFAULT_LON
                )

                record = {
                    "run_id": run_id,
                    "baseline_run_id": case["baseline_run_id"],
                    "crop": case["crop"],
                    "query": case["query"],
                    "condition": "governance_reject_disabled",
                    "wall_time_seconds": round(elapsed, 3),
                    "error": error,
                    "result": result,
                }
                dump_json(to_jsonable(record), result_path(GOVERNANCE_DIR, run_id))

                log_event({"phase": "governance_ablation", "run_id": run_id,
                            "status": "failed" if error else "completed",
                            "note": f"{round(elapsed, 1)}s"})
        finally:
            trustai.review = original_review
    finally:
        restore_state(backups)
        log_event({"phase": "governance_ablation", "run_id": "-", "status": "state_restored"})

    log_event({"phase": "governance_ablation", "run_id": "-", "status": "phase_complete"})


if __name__ == "__main__":
    main()
