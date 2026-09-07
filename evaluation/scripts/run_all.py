"""
Single entry point for the full research evaluation.

Runs, in order:
  1. Baseline matrix       (30 runs)  -- app/agents/*, orchestrator, governance
  2. Provider comparison   (~12 pairs)-- Ollama vs Groq, isolated per specialist call
  3. Agent ablation        (15 runs)  -- drop one specialist at a time
  4. Governance ablation   (3 runs)   -- TRUSTAI reject-gate disabled

Every phase is independently resumable (skips run_ids that already
have a saved result), so this script can be killed and re-run safely.
Progress streams to evaluation/run_log.jsonl as it goes.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness_utils import log_event  # noqa: E402

import run_baseline_matrix
import run_provider_comparison
import run_agent_ablation
import run_governance_ablation


def main():
    overall_start = time.time()
    log_event({"phase": "all", "run_id": "-", "status": "evaluation_started"})

    log_event({"phase": "all", "run_id": "-", "status": "phase_1_baseline_start"})
    run_baseline_matrix.main()

    log_event({"phase": "all", "run_id": "-", "status": "phase_2_provider_start"})
    run_provider_comparison.main()

    log_event({"phase": "all", "run_id": "-", "status": "phase_3_agent_ablation_start"})
    run_agent_ablation.main()

    log_event({"phase": "all", "run_id": "-", "status": "phase_4_governance_ablation_start"})
    run_governance_ablation.main()

    elapsed = time.time() - overall_start
    log_event({"phase": "all", "run_id": "-", "status": "evaluation_complete",
                "note": f"total {round(elapsed / 60, 1)} min"})


if __name__ == "__main__":
    main()
