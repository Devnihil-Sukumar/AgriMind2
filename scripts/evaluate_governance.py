"""
==========================================================================
AgriMind

TRUSTAI Evaluation Harness

Phase 12 starting point (bayesian.txt): measures the two central
claims of the governance layer over many runs --

    1. Intervention rate should fall as trust is earned (without a
       fixed threshold ever being touched).
    2. That decline should track a real posterior, not a random walk
       -- trust that climbs on sustained success and drops sharply on
       failure.

Two modes:

    --mode simulated (default)
        Feeds trustai a configurable synthetic outcome stream per
        category (no LLM calls, no network) so hundreds of runs
        complete in seconds. This is what makes a calibration curve
        practical to produce -- the real pipeline is far too slow
        (minutes per run) to call hundreds of times.

    --mode live
        Runs the real dynamic_orchestrator N times end to end. Slow
        (each run is a full LLM pipeline), intended for a small N to
        sanity-check the simulated curve against real agent behavior.

Both modes exercise the actual app.governance code -- nothing here
reimplements the Bayesian math, it only drives it and records what
comes out.

Usage
-----
    python -m scripts.evaluate_governance --runs 200
    python -m scripts.evaluate_governance --mode live --runs 5

Author : AgriMind Team
==========================================================================
"""

import argparse
import csv
import os
import random
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from app.governance.trustai import trustai, AGENT_CATEGORY
import json

from app.governance.trust_state import trust_state_store, TrustStateStore
from app.governance.audit_logger import audit_logger, GovernanceAuditLogger
from dataclasses import asdict


EVAL_STATE_PATH = os.path.join(
    "app", "governance", "state", "trust_state_eval.json"
)

EVAL_AUDIT_PATH = os.path.join(
    "logs", "trustai_evaluation_audit.jsonl"
)

EVAL_CSV_PATH = os.path.join(
    "logs", "trustai_evaluation.csv"
)

##########################################################################
# Default Outcome Distribution Per Category
#
# {status: probability}. "completed" also draws a confidence in
# [conf_low, conf_high]. These defaults describe a mostly-healthy
# system -- tune with --success-rate to model a flakier one.
##########################################################################

DEFAULT_OUTCOME_MODEL = {

    "data_collector": {
        "completed": 0.85,
        "unavailable": 0.10,
        "failed": 0.05,
        "conf_range": (0.70, 0.95)
    },

    "executive": {
        "completed": 0.90,
        "unavailable": 0.0,
        "failed": 0.10,
        "conf_range": (0.75, 0.95)
    },

    "recommendation": {
        "completed": 0.88,
        "unavailable": 0.0,
        "failed": 0.12,
        "conf_range": (0.75, 0.95)
    }

}


##########################################################################
# Isolated State (so an evaluation run never disturbs live trust
# accumulated from real pipeline usage)
##########################################################################

def use_isolated_state(defer_disk_writes=False):

    trust_state_store.path = EVAL_STATE_PATH
    trust_state_store._data = {"agents": {}, "categories": {}}

    audit_logger.path = EVAL_AUDIT_PATH

    if os.path.exists(EVAL_AUDIT_PATH):
        os.remove(EVAL_AUDIT_PATH)

    ################################################################
    # A simulated run can be thousands of evidence updates; writing
    # the full JSON state to disk after every single one (fine for a
    # real pipeline run, which only ever does a handful) turns a
    # few-second experiment into a multi-minute one. Persist once at
    # the end instead -- an evaluation run is disposable anyway.
    ################################################################

    ################################################################
    # Same reasoning for the audit logger: opening, appending to, and
    # closing a file 14,000+ times (Windows file-open overhead, often
    # compounded by antivirus scanning each call) is the difference
    # between a few seconds and several minutes. Buffer in memory and
    # flush once at the end instead.
    ################################################################

    buffer = []

    def buffered_log(record):
        buffer.append(record)

    if defer_disk_writes:
        trust_state_store._save = lambda: None
        audit_logger.log = buffered_log

    return buffer


def flush_audit_buffer(buffer):

    if not buffer:
        return

    os.makedirs(os.path.dirname(EVAL_AUDIT_PATH) or ".", exist_ok=True)

    with open(EVAL_AUDIT_PATH, "w", encoding="utf-8") as f:

        for record in buffer:

            entry = {
                "agent": record.agent,
                "category": record.category,
                "stage": record.stage,
                "prior_mean": round(record.prior_mean, 4),
                "posterior_mean": round(record.posterior_mean, 4),
                "evidence": (
                    asdict(record.evidence) if record.evidence else None
                ),
                "risk": asdict(record.risk),
                "decision": asdict(record.decision)
            }

            f.write(json.dumps(entry) + "\n")


##########################################################################
# Draw One Synthetic Outcome
##########################################################################

def draw_outcome(category, model, rng):

    profile = model[category]

    roll = rng.random()

    if roll < profile["failed"]:
        return {"status": "failed", "confidence": 0}

    if roll < profile["failed"] + profile["unavailable"]:
        return {"status": "unavailable", "confidence": 0}

    low, high = profile["conf_range"]

    return {
        "status": "completed",
        "confidence": round(rng.uniform(low, high), 2)
    }


##########################################################################
# Simulated Mode
##########################################################################

def run_simulated(runs, model, seed):

    audit_buffer = use_isolated_state(defer_disk_writes=True)

    rng = random.Random(seed)

    rows = []

    for run_index in range(1, runs + 1):

        for agent_name, category in AGENT_CATEGORY.items():

            outcome = draw_outcome(category, model, rng)

            record = trustai.record_outcome(agent_name, outcome)

            rows.append({
                "run": run_index,
                "agent": agent_name,
                "category": category,
                "outcome_status": outcome["status"],
                "action": record.decision.action,
                "p_fail": record.decision.p_fail,
                "trust_mean": round(record.posterior_mean, 4)
            })

    trust_state_store._save = TrustStateStore._save.__get__(trust_state_store)
    trust_state_store._save()

    audit_logger.log = GovernanceAuditLogger.log.__get__(audit_logger)
    flush_audit_buffer(audit_buffer)

    return rows


##########################################################################
# Live Mode
##########################################################################

def run_live(runs, reset):

    from app.orchestrator.dynamic_orchestrator import dynamic_orchestrator

    if reset:
        use_isolated_state()

    scenarios = [
        ("rice", "What should I do to maximize rice yield?"),
        ("cotton", "What should I do to maximize cotton yield?"),
        ("maize", "How can I improve my maize harvest?"),
    ]

    rows = []

    for run_index in range(1, runs + 1):

        crop, query = scenarios[(run_index - 1) % len(scenarios)]

        print(f"\n[live run {run_index}/{runs}] crop={crop}")

        result = dynamic_orchestrator.run(
            user_query=query,
            crop=crop,
            latitude=11.0168,
            longitude=76.9558
        )

        governance = result["execution"]["governance"]

        for agent_name, snapshot in governance["agent_trust"].items():

            rows.append({
                "run": run_index,
                "agent": agent_name,
                "category": snapshot["category"],
                "outcome_status": "",
                "action": "",
                "p_fail": "",
                "trust_mean": snapshot["trust_mean"]
            })

    return rows


##########################################################################
# Report
##########################################################################

def intervention_rate(rows, category, quartile_runs):

    subset = [
        r for r in rows
        if r["category"] == category
        and r["run"] in quartile_runs
        and r["action"]
    ]

    if not subset:
        return None

    governed = sum(
        1 for r in subset if r["action"] != "auto_execute"
    )

    return round(governed / len(subset), 3)


def print_report(rows, runs):

    print("\n" + "=" * 78)
    print("TRUSTAI EVALUATION REPORT")
    print("=" * 78)

    quartile_size = max(runs // 4, 1)

    first_quartile = set(range(1, quartile_size + 1))
    last_quartile = set(range(max(runs - quartile_size + 1, 1), runs + 1))

    categories = sorted(set(r["category"] for r in rows))

    print(
        f"\n{'Category':<16}"
        f"{'Intervention rate (first 25%)':<32}"
        f"{'Intervention rate (last 25%)':<32}"
    )

    for category in categories:

        first = intervention_rate(rows, category, first_quartile)
        last = intervention_rate(rows, category, last_quartile)

        print(
            f"{category:<16}"
            f"{str(first):<32}"
            f"{str(last):<32}"
        )

    print("\nFinal trust_mean per agent:")

    latest_run = max(r["run"] for r in rows)

    for r in rows:
        if r["run"] == latest_run:
            print(f"  {r['agent']:<20} {r['trust_mean']}")

    print(f"\nPer-run detail written to {EVAL_CSV_PATH}")


def write_csv(rows):

    os.makedirs(os.path.dirname(EVAL_CSV_PATH), exist_ok=True)

    with open(EVAL_CSV_PATH, "w", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run", "agent", "category",
                "outcome_status", "action", "p_fail", "trust_mean"
            ]
        )

        writer.writeheader()
        writer.writerows(rows)


##########################################################################
# Entry Point
##########################################################################

def main():

    parser = argparse.ArgumentParser(
        description="TRUSTAI intervention-rate / trust-calibration evaluation."
    )

    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--mode", choices=["simulated", "live"], default="simulated")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Live mode only: start from a clean isolated trust state "
             "instead of continuing whatever the live pipeline has "
             "already accumulated."
    )

    args = parser.parse_args()

    if args.mode == "simulated":
        rows = run_simulated(args.runs, DEFAULT_OUTCOME_MODEL, args.seed)
    else:
        rows = run_live(args.runs, args.reset)

    write_csv(rows)
    print_report(rows, args.runs)


if __name__ == "__main__":
    main()
