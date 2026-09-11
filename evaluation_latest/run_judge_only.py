"""
==========================================================================
AgriMind -- Standalone LLM-Judge Metrics (run on the machine that has the
generation model, so judge and generator are the SAME model)

Does NOT re-run the 105-scenario benchmark. It only reads the already-
saved results in evaluation_latest/results/raw/ and computes the three
metrics that require an LLM judge:

    - Agent F1 (per-agent risk/opportunity detection)
    - Recommendation Quality (1-5 Likert)
    - Hallucination Rate

Writes ONE standalone output file:
    evaluation_latest/results/llm_judge_metrics_<model>.json

Bring just that one file back -- nothing else needs to move between
machines for this step.

Usage
-----
    venv/Scripts/python.exe evaluation_latest/run_judge_only.py
==========================================================================
"""

import json
import os
import sys
import time

EVAL_LATEST_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_LATEST_ROOT)

# Force the judge onto the same model that generated the results, no
# matter what OLLAMA_MODEL happens to be set to in .env.
JUDGE_MODEL = os.getenv("AGRIMIND_JUDGE_MODEL", "qwen3:8b")
os.environ["OLLAMA_MODEL"] = JUDGE_MODEL

import metrics as M  # noqa: E402

RESULTS_DIR = os.path.join(EVAL_LATEST_ROOT, "results")
RAW_DIR = os.path.join(RESULTS_DIR, "raw")
OUT_PATH = os.path.join(
    RESULTS_DIR,
    f"llm_judge_metrics_{JUDGE_MODEL.replace(':', '-')}.json"
)


def main():
    print(f"Judge model: {JUDGE_MODEL}")

    if not os.path.isdir(RAW_DIR) or not os.listdir(RAW_DIR):
        print(f"ERROR: {RAW_DIR} is empty or missing. "
              f"This script reads already-saved results -- it does not "
              f"run the pipeline. Make sure the 420 result files from "
              f"the N=105 sweep are present there.")
        sys.exit(1)

    scenarios_by_id, _ = M.load_scenarios()
    all_results = M.load_results(RAW_DIR)
    full_system_results = [
        r for r in all_results
        if r.get("condition") == "full_system" and r.get("status") == "success"
    ]

    print(f"Loaded {len(all_results)} raw results "
          f"({len(full_system_results)} successful full_system).")

    t0 = time.time()
    print("Computing agent F1 scores...")
    agent_f1 = M.agent_f1_scores(all_results, scenarios_by_id)
    print(f"  done in {time.time() - t0:.1f}s")

    t1 = time.time()
    print("Computing recommendation quality...")
    rec_quality = M.recommendation_quality(full_system_results, scenarios_by_id)
    print(f"  done in {time.time() - t1:.1f}s")

    t2 = time.time()
    print("Computing hallucination rate...")
    halluc = M.hallucination_rate(full_system_results, scenarios_by_id)
    print(f"  done in {time.time() - t2:.1f}s")

    out = {
        "judge_model": JUDGE_MODEL,
        "n_full_system_results": len(full_system_results),
        "n_all_results": len(all_results),
        "total_seconds": round(time.time() - t0, 1),
        "agent_f1_scores": agent_f1,
        "recommendation_quality": rec_quality,
        "hallucination_rate": halluc,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    print()
    print(f"Wrote {OUT_PATH}")
    print(f"Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
