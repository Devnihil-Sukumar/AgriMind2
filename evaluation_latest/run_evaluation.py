"""
==========================================================================
AgriMind Research-Grade Evaluation — Single-Command Entry Point

    python evaluation_latest/run_evaluation.py

Builds the benchmark dataset if missing, runs every (scenario x condition)
pair (resumable -- safe to re-run after an interruption, only completed
pairs are skipped), computes all 8 metrics, writes the 4 result tables,
renders the 4 figures at 300 DPI, and writes the final Markdown report.

Each stage is independently re-runnable: `python metrics.py` alone
recomputes tables/figures/report from whatever is already in results/raw/
without re-running the pipeline.
==========================================================================
"""

import json
import os
import sys

EVAL_LATEST_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_LATEST_ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import evaluator  # noqa: E402
import compute_and_report  # noqa: E402


def main():
    print("=" * 70)
    print("STEP 1/3 -- ensuring benchmark dataset exists")
    print("=" * 70)
    dataset_path = os.path.join(EVAL_LATEST_ROOT, "dataset", "benchmark_queries.json")
    if not os.path.exists(dataset_path):
        import build_dataset  # noqa
    with open(dataset_path, "r", encoding="utf-8") as f:
        n = json.load(f)["n_scenarios"]
    print(f"Dataset ready: {n} scenarios.")

    print("=" * 70)
    print("STEP 2/3 -- running evaluation (resumable, may take hours)")
    print("=" * 70)
    evaluator.main()

    print("=" * 70)
    print("STEP 3/3 -- computing metrics, tables, figures, report")
    print("=" * 70)
    compute_and_report.main()

    print("Done. See evaluation_latest/reports/ and evaluation_latest/figures/.")


if __name__ == "__main__":
    main()
