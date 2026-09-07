"""
==========================================================================
AgriMind Research-Grade Evaluation — Evaluator / Orchestration Loop

Runs every (scenario x condition) pair, checkpointed (only a successful
result counts as "done" -- a failed/errored run is retried on resume,
matching a lesson learned the hard way in the earlier evaluation/
harness). Saves one raw JSON per pair to results/raw/. A SIGTERM handler
converts a hard stop into the same clean-shutdown path as Ctrl-C.
==========================================================================
"""

import argparse
import json
import os
import shutil
import signal
import sys
import time
import traceback

EVAL_LATEST_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_LATEST_ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt(f"received signal {signum}")


try:
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
except (ValueError, AttributeError, OSError):
    pass

import baselines  # noqa: E402

RESULTS_DIR = os.path.join(EVAL_LATEST_ROOT, "results")
RAW_DIR = os.path.join(RESULTS_DIR, "raw")
LOG_PATH = os.path.join(RESULTS_DIR, "run_log.jsonl")
os.makedirs(RAW_DIR, exist_ok=True)

CONDITIONS_ORDER = ["single_agent", "multi_no_reasoning", "multi_with_reasoning", "full_system"]

PROJECT_ROOT = os.path.dirname(EVAL_LATEST_ROOT)
TRUST_STATE_PATH = os.path.join(PROJECT_ROOT, "app", "governance", "state", "trust_state.json")
LEARNING_STATE_PATH = os.path.join(PROJECT_ROOT, "app", "governance", "state", "crop_learning_state.json")


def backup_state():
    """condition_4/full_system is the real, unmodified pipeline, so it
    genuinely calls TRUSTAI -- which means it would otherwise mix
    synthetic-benchmark outcomes into the production trust state used
    by real requests. Back it up before running, restore after
    (unconditionally, via finally), same pattern used in the earlier
    evaluation/ harness after learning this the hard way there."""
    backups = {}
    for path in (TRUST_STATE_PATH, LEARNING_STATE_PATH):
        if os.path.exists(path):
            backup = path + ".bak"
            shutil.copy2(path, backup)
            backups[path] = backup
    return backups


def restore_state(backups):
    for path, backup in backups.items():
        if os.path.exists(backup):
            shutil.copy2(backup, path)
            os.remove(backup)


def log_event(event):
    event = dict(event)
    event["ts"] = time.time()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    print(f"[{event.get('status','')}] {event.get('scenario_id','')} / {event.get('condition','')} {event.get('note','')}".strip())


def _default(o):
    return str(o)


def result_path(scenario_id, condition):
    return os.path.join(RAW_DIR, f"{scenario_id}__{condition}.json")


def is_degraded(record):
    """True when a run completed only by falling back off an LLM path
    somewhere in the pipeline -- specialists, collaborative reasoning,
    or recommendation generation.

    AgriMind is built to degrade gracefully, which is a virtue in
    production and a hazard in evaluation: a quota-exhausted provider
    still returns status="success" while a stage silently ran
    deterministic instead of reasoned. Two separate incidents during the
    50-scenario run, both caught only by manually inspecting individual
    results rather than trusting the "success" status:

      1. Groq's daily token quota ran out: recommendation.generation_mode
         became "deterministic_fallback" (confidence 0.35) with a failed
         SoilAgent -- vegetation_critical_yield_rice.
      2. Gemini's free tier caps at 20 requests/DAY (far tighter than
         Groq's ~200k-token budget), and collaborative reasoning calls
         it once per scenario. After the 3rd scenario, 12 of the next 12
         silently ran on collaborative_engine's deterministic consensus
         path instead of real Gemini reasoning -- invisible in
         recommendation.generation_mode and in every specialist's own
         status, since only the reasoning STAGE degraded. Caught by
         grepping raw results for reasoning containing "Deterministic
         consensus generated because Gemini reasoning was unavailable."
         (see app/reasoning/collaborative_engine.py) after noticing
         Gemini 429s in the terminal -- not by any automated check.

    Any such run measures fallback behaviour, not system quality, and
    caching it as "done" would silently bake degraded data into the
    published metrics. It is therefore NOT counted as done, so a later
    resume with fresh quota re-runs it properly.
    """
    recommendation = record.get("recommendation") or {}

    if recommendation.get("generation_mode") == "deterministic_fallback":
        return True

    specialists = record.get("specialists") or {}

    if any(
        (output or {}).get("status") in ("failed", "rejected")
        for output in specialists.values()
    ):
        return True

    reasoning = record.get("reasoning")

    if "Deterministic consensus generated" in str(reasoning):
        return True

    return False


def already_done(scenario_id, condition):
    path = result_path(scenario_id, condition)
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        if record.get("status") != "success":
            return False
        return not is_degraded(record)
    except (json.JSONDecodeError, OSError):
        return False


def run_all(scenarios, conditions=None):
    conditions = conditions or CONDITIONS_ORDER
    total = len(scenarios) * len(conditions)
    log_event({"status": "started", "note": f"{len(scenarios)} scenarios x {len(conditions)} conditions = {total} runs"})

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        for condition in conditions:
            if already_done(sid, condition):
                log_event({"status": "skipped_cached", "scenario_id": sid, "condition": condition})
                continue

            log_event({"status": "running", "scenario_id": sid, "condition": condition})
            start = time.time()
            try:
                result = baselines.CONDITIONS[condition](scenario)
            except KeyboardInterrupt:
                # A deliberate stop (Ctrl-C or SIGTERM, converted above).
                # Log it as a clean interruption, then re-raise so
                # main()'s finally still restores TRUSTAI state and the
                # process exits via the normal interrupted path rather
                # than an uncaught crash.
                log_event({"status": "interrupted", "scenario_id": sid, "condition": condition,
                           "note": f"{round(time.time() - start, 2)}s"})
                raise
            except Exception as e:
                result = {"status": "error", "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                          "condition": condition}
            elapsed = round(time.time() - start, 2)
            result["scenario_id"] = sid
            result["wall_time_seconds"] = elapsed

            with open(result_path(sid, condition), "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=_default)

            log_event({"status": result.get("status", "unknown"), "scenario_id": sid, "condition": condition,
                       "note": f"{elapsed}s" + (f" ERROR: {result.get('error', '')[:150]}" if result.get("status") == "error" else "")})

    log_event({"status": "phase_complete"})


def main():
    """--conditions restricts the run to a subset of the four ablation
    conditions, e.g.

        python evaluation_latest/evaluator.py --conditions full_system

    This exists because the four conditions together need roughly three
    days of Groq's free-tier daily token budget (a full 40-pair sweep
    exhausted 200k TPD after 14 pairs). Restricting to full_system
    refreshes the eight headline metrics -- Tables 1/2/3 and every
    figure read only that condition -- within a single day's quota,
    leaving the Table 4 ablation to be refreshed separately."""

    parser = argparse.ArgumentParser(
        description="Run the AgriMind research benchmark (checkpointed; "
                    "re-running only retries pairs that have not yet succeeded)."
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=CONDITIONS_ORDER,
        default=CONDITIONS_ORDER,
        help="Conditions to run (default: all four)."
    )
    args = parser.parse_args()

    dataset_path = os.path.join(EVAL_LATEST_ROOT, "dataset", "benchmark_queries.json")
    if not os.path.exists(dataset_path):
        import subprocess
        subprocess.run([sys.executable, os.path.join(EVAL_LATEST_ROOT, "dataset", "build_dataset.py")], check=True)

    with open(dataset_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]

    backups = backup_state()
    log_event({"status": "state_backed_up", "note": f"conditions={args.conditions}"})
    try:
        run_all(scenarios, conditions=args.conditions)
    finally:
        restore_state(backups)
        log_event({"status": "state_restored"})


if __name__ == "__main__":
    main()
