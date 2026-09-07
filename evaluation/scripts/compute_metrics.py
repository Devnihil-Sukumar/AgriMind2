"""
Loads every raw evaluation result (baseline matrix, provider
comparison, agent ablation, governance ablation) and computes the
research-level metrics described in evaluation/metrics.md, writing:

  evaluation/tables/*.csv    -- flat tables for the paper
  evaluation/figures/*.png   -- plots for the paper

Run this AFTER the run_*.py scripts have produced data. Safe to
re-run any time; it only reads evaluation/data/**, never mutates it.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from harness_utils import (  # noqa: E402
    EVAL_ROOT, RAW_DIR, PROVIDER_DIR, ABLATION_DIR, GOVERNANCE_DIR,
)

TABLES_DIR = os.path.join(EVAL_ROOT, "tables")
FIGURES_DIR = os.path.join(EVAL_ROOT, "figures")
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 10,
})

SPECIALISTS = ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent"]
STAGE_AGENTS = SPECIALISTS + ["ExecutiveAgent", "RecommendationAgent"]


##########################################################################
# Loading
##########################################################################

def load_dir(directory):
    records = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return records


def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


##########################################################################
# 1. Reliability + latency (baseline matrix)
##########################################################################

def build_run_level_table(raw_records):
    rows = []
    for rec in raw_records:
        result = rec.get("result")
        row = {
            "run_id": rec["run_id"],
            "crop": rec["crop"],
            "query_type": safe_get(rec, "meta", "query_type"),
            "repeat": safe_get(rec, "meta", "repeat"),
            "wall_time_seconds": rec["wall_time_seconds"],
            "pipeline_error": rec["error"] is not None,
        }
        if result is not None:
            execution = result.get("execution", {})
            stats = execution.get("statistics", {})
            row.update({
                "status": result.get("status"),
                "overall_confidence": execution.get("confidence"),
                "agents_planned": stats.get("agents_planned"),
                "agents_completed": stats.get("agents_completed"),
                "agents_failed": stats.get("agents_failed"),
                "agents_unavailable": stats.get("agents_unavailable"),
                "planner_confidence": stats.get("planner_confidence"),
                "reasoning_confidence": stats.get("reasoning_confidence"),
                "executive_confidence": stats.get("executive_confidence"),
                "explanation_confidence": stats.get("explanation_confidence"),
                "decision_trace_steps": stats.get("decision_trace_steps"),
                "evidence_sources": stats.get("evidence_sources"),
                "limitations_count": stats.get("limitations"),
                "monitoring_items": stats.get("monitoring_items"),
                "recommendation_generation_mode": safe_get(
                    execution, "recommendation", "generation_mode"),
                "recommendation_requires_review": safe_get(
                    execution, "governance", "recommendation_requires_review"),
                "recommendation_rejected": safe_get(
                    execution, "governance", "recommendation_rejected"),
            })
        else:
            row.update({"status": "pipeline_error"})
        rows.append(row)
    return pd.DataFrame(rows)


def build_agent_level_table(raw_records):
    rows = []
    for rec in raw_records:
        result = rec.get("result")
        if result is None:
            continue
        specialists = safe_get(result, "execution", "specialists", default={})
        for agent_name, out in specialists.items():
            gov = out.get("governance", {}) or {}
            decision = gov.get("decision", {}) or {}
            rows.append({
                "run_id": rec["run_id"],
                "crop": rec["crop"],
                "query_type": safe_get(rec, "meta", "query_type"),
                "agent": agent_name,
                "status": out.get("status"),
                "confidence": out.get("confidence"),
                "execution_time": out.get("execution_time"),
                "num_risks": len(out.get("risks", []) or []),
                "num_opportunities": len(out.get("opportunities", []) or []),
                "governance_action": decision.get("action"),
                "governance_p_fail": decision.get("p_fail"),
                "posterior_mean": gov.get("posterior_mean"),
            })
        # executive + recommendation as pseudo-agents for latency/status tracking
        executive = safe_get(result, "execution", "executive", default={}) or {}
        rows.append({
            "run_id": rec["run_id"], "crop": rec["crop"],
            "query_type": safe_get(rec, "meta", "query_type"),
            "agent": "ExecutiveAgent", "status": executive.get("status"),
            "confidence": executive.get("confidence"),
            "execution_time": executive.get("execution_time"),
            "num_risks": None, "num_opportunities": None,
            "governance_action": safe_get(executive, "governance", "decision", "action"),
            "governance_p_fail": safe_get(executive, "governance", "decision", "p_fail"),
            "posterior_mean": safe_get(executive, "governance", "posterior_mean"),
        })
        recommendation = safe_get(result, "execution", "recommendation", default={}) or {}
        rows.append({
            "run_id": rec["run_id"], "crop": rec["crop"],
            "query_type": safe_get(rec, "meta", "query_type"),
            "agent": "RecommendationAgent", "status": recommendation.get("status"),
            "confidence": recommendation.get("confidence"),
            "execution_time": None,
            "num_risks": None, "num_opportunities": None,
            "governance_action": safe_get(recommendation, "governance", "decision", "action"),
            "governance_p_fail": safe_get(recommendation, "governance", "decision", "p_fail"),
            "posterior_mean": safe_get(recommendation, "governance", "posterior_mean"),
        })
    return pd.DataFrame(rows)


def build_trust_snapshot_table(raw_records):
    """Last observed TRUSTAI snapshot per run, in chronological (file) order."""
    rows = []
    for rec in raw_records:
        result = rec.get("result")
        if result is None:
            continue
        agent_trust = safe_get(result, "execution", "governance", "agent_trust", default={})
        for agent_name, t in (agent_trust or {}).items():
            rows.append({
                "run_id": rec["run_id"],
                "agent": agent_name,
                "category": t.get("category"),
                "trust_mean": t.get("trust_mean"),
                "trust_std": t.get("trust_std"),
            })
    return pd.DataFrame(rows)


##########################################################################
# 2. Provider comparison
##########################################################################

def build_provider_table(provider_records):
    rows = []
    for rec in provider_records:
        for provider in ("ollama", "groq"):
            p = rec.get(provider, {})
            rows.append({
                "run_id": rec["run_id"],
                "crop": rec["crop"],
                "agent": rec["agent"],
                "provider": provider,
                "elapsed_seconds": p.get("elapsed_seconds"),
                "valid_json_first_try": p.get("valid_json_first_try"),
                "error": p.get("error"),
                "response_chars": p.get("response_chars"),
            })
    return pd.DataFrame(rows)


##########################################################################
# 3. Ablation tables
##########################################################################

def build_ablation_table(ablation_records, raw_by_id):
    rows = []
    for rec in ablation_records:
        result = rec.get("result")
        baseline = raw_by_id.get(rec.get("baseline_run_id"))
        baseline_result = baseline.get("result") if baseline else None

        def conf(res):
            return safe_get(res, "execution", "confidence") if res else None

        rows.append({
            "run_id": rec["run_id"],
            "baseline_run_id": rec.get("baseline_run_id"),
            "crop": rec["crop"],
            "dropped_agent": rec.get("dropped_agent"),
            "wall_time_seconds": rec.get("wall_time_seconds"),
            "error": rec.get("error") is not None,
            "ablated_confidence": conf(result),
            "baseline_confidence": conf(baseline_result),
            "confidence_delta": (
                (conf(result) - conf(baseline_result))
                if conf(result) is not None and conf(baseline_result) is not None
                else None
            ),
            "ablated_status": safe_get(result, "status") if result else None,
        })
    return pd.DataFrame(rows)


def build_governance_ablation_table(gov_records, raw_by_id):
    rows = []
    for rec in gov_records:
        result = rec.get("result")
        baseline = raw_by_id.get(rec.get("baseline_run_id"))
        baseline_result = baseline.get("result") if baseline else None

        def stats_of(res):
            return safe_get(res, "execution", "statistics", default={}) or {}

        s_off, s_base = stats_of(result), stats_of(baseline_result)
        rows.append({
            "run_id": rec["run_id"],
            "baseline_run_id": rec.get("baseline_run_id"),
            "crop": rec["crop"],
            "confidence_governed": safe_get(baseline_result, "execution", "confidence"),
            "confidence_ungoverned": safe_get(result, "execution", "confidence"),
            "agents_completed_governed": s_base.get("agents_completed"),
            "agents_completed_ungoverned": s_off.get("agents_completed"),
            "review_required_governed": safe_get(
                baseline_result, "execution", "governance", "recommendation_requires_review"),
            "review_required_ungoverned": safe_get(
                result, "execution", "governance", "recommendation_requires_review"),
        })
    return pd.DataFrame(rows)


##########################################################################
# Figures
##########################################################################

def fig_latency_by_stage(run_df, agent_df, path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    axes[0].hist(run_df["wall_time_seconds"].dropna() / 60, bins=15, color="#2f9e5b")
    axes[0].set_xlabel("End-to-end wall time (minutes)")
    axes[0].set_ylabel("Number of runs")
    axes[0].set_title("Full-pipeline latency distribution")

    agent_lat = agent_df.dropna(subset=["execution_time"]).groupby("agent")["execution_time"].agg(
        ["mean", "std", "count"])
    agent_lat = agent_lat.reindex([a for a in STAGE_AGENTS if a in agent_lat.index])
    axes[1].bar(agent_lat.index, agent_lat["mean"], yerr=agent_lat["std"].fillna(0),
                color="#217a47", capsize=4)
    axes[1].set_ylabel("Mean execution time (s)")
    axes[1].set_title("Per-agent latency (mean +/- std)")
    axes[1].tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_reliability(agent_df, path):
    status_counts = agent_df.groupby(["agent", "status"]).size().unstack(fill_value=0)
    status_counts = status_counts.reindex([a for a in STAGE_AGENTS if a in status_counts.index])
    status_colors = {"completed": "#2f9e5b", "failed": "#b3352b",
                      "unavailable": "#b9791b", "rejected": "#8a978d"}
    colors = [status_colors.get(col, "#5b6b60") for col in status_counts.columns]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    status_counts.plot(kind="bar", stacked=True, ax=ax, color=colors)
    ax.set_ylabel("Number of runs")
    ax.set_title("Agent outcome distribution across all evaluation runs")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="status")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_confidence_calibration(agent_df, path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    data = [agent_df.loc[agent_df["agent"] == a, "confidence"].dropna()
            for a in STAGE_AGENTS if a in agent_df["agent"].unique()]
    labels = [a for a in STAGE_AGENTS if a in agent_df["agent"].unique()]
    ax.boxplot(data, tick_labels=labels, showmeans=True)
    ax.set_ylabel("Reported confidence")
    ax.set_title("Confidence distribution per agent")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_trust_evolution(trust_df, path):
    if trust_df.empty:
        return
    trust_df = trust_df.copy()
    trust_df["order"] = trust_df.groupby("agent").cumcount()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for agent, g in trust_df.groupby("agent"):
        ax.plot(g["order"], g["trust_mean"], marker="o", markersize=3, label=agent)
    ax.set_xlabel("Observation index (chronological)")
    ax.set_ylabel("TRUSTAI posterior trust mean")
    ax.set_title("Trust posterior evolution across the evaluation session")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_provider_comparison(provider_df, path):
    if provider_df.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    lat = provider_df.dropna(subset=["elapsed_seconds"]).groupby("provider")["elapsed_seconds"].agg(
        ["mean", "std"])
    axes[0].bar(lat.index, lat["mean"], yerr=lat["std"].fillna(0), color=["#2f9e5b", "#2563a8"],
                capsize=5)
    axes[0].set_ylabel("Mean latency (s)")
    axes[0].set_title("Ollama vs Groq: per-call latency")

    valid_rate = provider_df.groupby("provider")["valid_json_first_try"].mean()
    axes[1].bar(valid_rate.index, valid_rate.values * 100, color=["#2f9e5b", "#2563a8"])
    axes[1].set_ylabel("First-try valid JSON rate (%)")
    axes[1].set_ylim(0, 105)
    axes[1].set_title("Ollama vs Groq: structured-output reliability")

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_agent_ablation(ablation_df, path):
    if ablation_df.empty:
        return
    grouped = ablation_df.groupby("dropped_agent")["confidence_delta"].agg(["mean", "std", "count"])
    grouped = grouped.reindex([a for a in SPECIALISTS if a in grouped.index])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(grouped.index, grouped["mean"], yerr=grouped["std"].fillna(0),
           color="#b3352b", capsize=4)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Change in overall confidence\n(ablated - baseline)")
    ax.set_title("Agent contribution: confidence drop when removed")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_governance_ablation(gov_df, path):
    if gov_df.empty:
        return
    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = np.arange(len(gov_df))
    width = 0.35
    ax.bar(x - width / 2, gov_df["confidence_governed"], width, label="Governed", color="#2f9e5b")
    ax.bar(x + width / 2, gov_df["confidence_ungoverned"], width, label="Ungoverned", color="#b9791b")
    ax.set_xticks(x)
    ax.set_xticklabels(gov_df["crop"])
    ax.set_ylabel("Overall confidence")
    ax.set_title("TRUSTAI governance on vs off")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


##########################################################################
# Main
##########################################################################

def main():
    raw_records = load_dir(RAW_DIR)
    provider_records = load_dir(PROVIDER_DIR)
    ablation_records = load_dir(ABLATION_DIR)
    gov_records = load_dir(GOVERNANCE_DIR)

    raw_by_id = {r["run_id"]: r for r in raw_records}

    run_df = build_run_level_table(raw_records)
    agent_df = build_agent_level_table(raw_records)
    trust_df = build_trust_snapshot_table(raw_records)
    provider_df = build_provider_table(provider_records)
    ablation_df = build_ablation_table(ablation_records, raw_by_id)
    gov_df = build_governance_ablation_table(gov_records, raw_by_id)

    run_df.to_csv(os.path.join(TABLES_DIR, "run_level.csv"), index=False)
    agent_df.to_csv(os.path.join(TABLES_DIR, "agent_level.csv"), index=False)
    trust_df.to_csv(os.path.join(TABLES_DIR, "trust_snapshots.csv"), index=False)
    provider_df.to_csv(os.path.join(TABLES_DIR, "provider_comparison.csv"), index=False)
    ablation_df.to_csv(os.path.join(TABLES_DIR, "agent_ablation.csv"), index=False)
    gov_df.to_csv(os.path.join(TABLES_DIR, "governance_ablation.csv"), index=False)

    # Summary tables (paper-ready aggregates)
    if not run_df.empty:
        run_summary = run_df.groupby("query_type").agg(
            n=("run_id", "count"),
            mean_wall_time_s=("wall_time_seconds", "mean"),
            std_wall_time_s=("wall_time_seconds", "std"),
            mean_confidence=("overall_confidence", "mean"),
            std_confidence=("overall_confidence", "std"),
            pipeline_error_rate=("pipeline_error", "mean"),
        ).round(3)
        run_summary.to_csv(os.path.join(TABLES_DIR, "summary_by_query_type.csv"))

    if not agent_df.empty:
        agent_summary = agent_df.groupby("agent").agg(
            n=("run_id", "count"),
            success_rate=("status", lambda s: (s == "completed").mean()),
            mean_confidence=("confidence", "mean"),
            std_confidence=("confidence", "std"),
            mean_execution_time_s=("execution_time", "mean"),
            mean_posterior_trust=("posterior_mean", "mean"),
        ).round(3)
        agent_summary = agent_summary.reindex(
            [a for a in STAGE_AGENTS if a in agent_summary.index])
        agent_summary.to_csv(os.path.join(TABLES_DIR, "summary_by_agent.csv"))

    if not provider_df.empty:
        provider_summary = provider_df.groupby("provider").agg(
            n=("run_id", "count"),
            mean_latency_s=("elapsed_seconds", "mean"),
            std_latency_s=("elapsed_seconds", "std"),
            valid_json_first_try_rate=("valid_json_first_try", "mean"),
        ).round(3)
        provider_summary.to_csv(os.path.join(TABLES_DIR, "summary_by_provider.csv"))

    # Figures
    if not run_df.empty and not agent_df.empty:
        fig_latency_by_stage(run_df, agent_df, os.path.join(FIGURES_DIR, "latency.png"))
        fig_reliability(agent_df, os.path.join(FIGURES_DIR, "reliability.png"))
        fig_confidence_calibration(agent_df, os.path.join(FIGURES_DIR, "confidence_by_agent.png"))
    fig_trust_evolution(trust_df, os.path.join(FIGURES_DIR, "trust_evolution.png"))
    fig_provider_comparison(provider_df, os.path.join(FIGURES_DIR, "provider_comparison.png"))
    fig_agent_ablation(ablation_df, os.path.join(FIGURES_DIR, "agent_ablation.png"))
    fig_governance_ablation(gov_df, os.path.join(FIGURES_DIR, "governance_ablation.png"))

    print(f"raw runs: {len(raw_records)}  provider pairs: {len(provider_records)}  "
          f"agent-ablation runs: {len(ablation_records)}  governance-ablation runs: {len(gov_records)}")
    print(f"Tables written to {TABLES_DIR}")
    print(f"Figures written to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
