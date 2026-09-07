"""
==========================================================================
AgriMind Research-Grade Evaluation — Metric Computation

Implements the 8 metrics against raw results produced by evaluator.py.
Every function states its own N and, for proportions, a Wilson score
confidence interval (behaves reasonably at small N, unlike a naive
normal-approximation interval). Nothing here invents a number it cannot
compute from the raw data: LLM-judge-based metrics (agent F1,
recommendation quality, hallucination rate) call Groq explicitly and
are labeled as such everywhere they're reported.
==========================================================================
"""

import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def wilson_ci(successes, n, z=1.96):
    """Wilson score interval for a proportion. Returns (low, high) in [0,1].
    Chosen over a normal approximation because it stays well-behaved for
    the small sample sizes (N=10) used throughout this benchmark."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n)) / n)
    low = (centre - adj) / denom
    high = (centre + adj) / denom
    return (round(max(0.0, low), 4), round(min(1.0, high), 4))


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * (p / 100)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] + (values[c] - values[f]) * (k - f)


def safe_get(d, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


# ==========================================================================
# 1. Task Success Rate
# ==========================================================================

def task_success_rate(full_system_results):
    n = len(full_system_results)
    successes = sum(1 for r in full_system_results if r.get("status") == "success" and r.get("recommendation"))
    rate = round(100 * successes / n, 2) if n else 0.0
    lo, hi = wilson_ci(successes, n)
    return {"metric": "Task Success Rate", "n": n, "successes": successes,
            "value_pct": rate, "ci_95": [round(lo * 100, 2), round(hi * 100, 2)]}


# ==========================================================================
# 2. Decision Accuracy
# ==========================================================================

def decision_accuracy(full_system_results, scenarios_by_id):
    """Reported two ways, because the benchmark deliberately contains
    scenarios that probe a documented capability gap.

    A soil-pH excursion warrants inspection agronomically, but
    executive_engine.infer_decision() has no pH branch and can only
    answer "Continue Monitoring". Those scenarios carry
    probes_known_limitation=True and are EXPECTED to fail. Folding them
    into one number would silently depress the headline figure and
    leave a reader unable to tell a capability gap from ordinary error,
    so both figures are reported: the honest overall rate, and the rate
    over scenarios the system is actually built to handle.
    """
    n = 0
    correct = 0
    n_core = 0
    correct_core = 0
    rows = []
    for r in full_system_results:
        sid = r["scenario_id"]
        scenario = scenarios_by_id.get(sid)
        if not scenario or r.get("status") != "success":
            continue
        n += 1
        actual = safe_get(r, "executive", "decision") or ""
        expected = scenario["ground_truth_decision"]
        is_correct = actual.strip().lower() == expected.strip().lower()
        correct += int(is_correct)

        probe = bool(scenario.get("probes_known_limitation"))

        if not probe:
            n_core += 1
            correct_core += int(is_correct)

        rows.append({"scenario_id": sid, "expected": expected, "actual": actual,
                      "correct": is_correct, "probes_known_limitation": probe})

    rate = round(100 * correct / n, 2) if n else 0.0
    lo, hi = wilson_ci(correct, n)

    core_rate = round(100 * correct_core / n_core, 2) if n_core else None
    core_lo, core_hi = wilson_ci(correct_core, n_core) if n_core else (0, 0)

    n_probes = n - n_core
    probes_passed = correct - correct_core

    return {"metric": "Decision Accuracy", "n": n, "correct": correct,
            "value_pct": rate, "ci_95": [round(lo * 100, 2), round(hi * 100, 2)],
            "excluding_known_limitation_probes": {
                "n": n_core,
                "correct": correct_core,
                "value_pct": core_rate,
                "ci_95": [round(core_lo * 100, 2), round(core_hi * 100, 2)],
            },
            "known_limitation_probes": {
                "n": n_probes,
                "passed": probes_passed,
                "note": "Soil-pH scenarios: no pH branch exists in "
                        "executive_engine.infer_decision(), so these are "
                        "expected to fail and measure a capability gap, "
                        "not noise.",
            },
            "rows": rows}


# ==========================================================================
# 3. Routing Accuracy
# ==========================================================================

def _unavailable_agents(scenario):
    """Agents whose underlying data source carries nothing usable in this
    scenario's fixture, so a planner that skips them is behaving
    CORRECTLY rather than missing them.

    This exists because the benchmark's expected_agents field is a static
    query-type -> agent-set mapping (see build_dataset.py) that takes no
    account of whether a source actually has data. Every scenario in this
    benchmark clones a context whose historical table is empty
    (record_count == 0), and two scenarios additionally carry a failed
    market collection -- so the static mapping "expects" HistoricalAgent
    in 5 scenarios and MarketAgent in 1 where there is literally nothing
    for those agents to analyse. Scoring the planner against the static
    set penalised it for correctly declining to invoke an agent over an
    empty data source, which measured the benchmark's own blind spot
    rather than the planner's routing quality. Both figures are reported
    so the size of that correction stays visible.
    """
    fixture = scenario.get("fixture", {}) or {}
    unavailable = set()

    historical = fixture.get("historical", {}) or {}
    if not (historical.get("record_count") or 0):
        unavailable.add("HistoricalAgent")

    for source, agent in (("weather", "WeatherAgent"), ("soil", "SoilAgent"),
                          ("satellite", "SatelliteAgent"), ("market", "MarketAgent")):
        if (fixture.get(source, {}) or {}).get("status") != "success":
            unavailable.add(agent)

    return unavailable


def routing_accuracy(full_system_results, scenarios_by_id):
    n = 0
    exact_matches = 0
    exact_matches_static = 0
    per_agent = {a: {"tp": 0, "fp": 0, "fn": 0} for a in
                 ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent"]}
    unnecessary_total, missed_total, planned_total, expected_total = 0, 0, 0, 0
    rows = []

    for r in full_system_results:
        sid = r["scenario_id"]
        scenario = scenarios_by_id.get(sid)
        if not scenario or r.get("status") != "success":
            continue
        n += 1
        expected_static = set(scenario["expected_agents"])
        expected = expected_static - _unavailable_agents(scenario)
        plan_agents = {
            step.get("agent") for step in (r.get("plan") or {}).get("execution_plan", [])
            if step.get("agent") not in (None, "RecommendationAgent", "ExecutiveAgent")
        }
        actual = plan_agents or set(r.get("specialists", {}).keys())

        exact_matches += int(expected == actual)
        exact_matches_static += int(expected_static == actual)
        unnecessary = actual - expected
        missed = expected - actual
        unnecessary_total += len(unnecessary)
        missed_total += len(missed)
        planned_total += len(actual)
        expected_total += len(expected)

        for agent in per_agent:
            in_expected, in_actual = agent in expected, agent in actual
            if in_actual and in_expected:
                per_agent[agent]["tp"] += 1
            elif in_actual and not in_expected:
                per_agent[agent]["fp"] += 1
            elif in_expected and not in_actual:
                per_agent[agent]["fn"] += 1

        rows.append({"scenario_id": sid, "expected": sorted(expected),
                      "expected_static": sorted(expected_static),
                      "unavailable_excluded": sorted(expected_static - expected),
                      "actual": sorted(actual),
                      "exact_match": expected == actual, "unnecessary": sorted(unnecessary),
                      "missed": sorted(missed)})

    per_agent_scores = {}
    for agent, c in per_agent.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else None
        recall = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else None
        per_agent_scores[agent] = {
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
        }

    exact_rate = round(100 * exact_matches / n, 2) if n else 0.0
    lo, hi = wilson_ci(exact_matches, n)
    static_rate = round(100 * exact_matches_static / n, 2) if n else 0.0
    return {
        "metric": "Routing Accuracy", "n": n, "exact_matches": exact_matches,
        "exact_match_rate_pct": exact_rate, "ci_95": [round(lo * 100, 2), round(hi * 100, 2)],
        "ground_truth": "availability-aware (agents with no usable source data are not expected)",
        "exact_match_rate_pct_static_ground_truth": static_rate,
        "static_ground_truth_note":
            "Scoring against the raw query-type->agent mapping, which ignores whether a "
            "source has data, gives "
            f"{static_rate}% -- the gap to {exact_rate}% is the benchmark's own blind spot, "
            "not planner error. See _unavailable_agents().",
        "unnecessary_agent_rate_pct": round(100 * unnecessary_total / planned_total, 2) if planned_total else 0.0,
        "missed_agent_rate_pct": round(100 * missed_total / expected_total, 2) if expected_total else 0.0,
        "per_agent": per_agent_scores, "rows": rows,
    }


# ==========================================================================
# 4. Individual Agent F1-score (LLM-judge against dataset ground truth)
# ==========================================================================

JUDGE_RISK_PROMPT = """You are auditing an AI agricultural specialist agent's output against a known ground-truth condition.

GROUND TRUTH: the following condition IS present in this scenario: "{condition_description}"
Keywords that would indicate correct detection: {keywords}

AGENT'S STATED ANALYSIS:
{analysis}

AGENT'S STATED RISKS: {risks}
AGENT'S STATED OPPORTUNITIES: {opportunities}

Judge DETECTION ONLY. This agent is a specialist whose job is to observe and
report the condition in its own domain. Prescribing the remedy is a different
component's job, so do NOT require the agent to recommend any corrective
action, treatment, product or next step. If the agent identified the condition
(even worded differently, and even with no recommendation attached), that is
detected = true.

Did the agent's output correctly identify this specific condition?
Answer with ONLY a single JSON object: {{"detected": true or false, "reason": "one short sentence"}}
"""


def _llm_judge_detected(condition_description, keywords, analysis, risks, opportunities):
    from app.utils.groq_client import groq_client
    from app.utils.json_extract import extract_json_object

    prompt = JUDGE_RISK_PROMPT.format(
        condition_description=condition_description, keywords=", ".join(keywords) or "(none -- absence expected)",
        analysis=(analysis or "")[:800], risks=risks or [], opportunities=opportunities or [])
    try:
        raw = groq_client.generate(prompt=prompt, temperature=0.0, max_tokens=700)
        result = extract_json_object(raw, error_label="agent_f1_judge")
        return bool(result.get("detected")), result.get("reason", "")
    except Exception as e:
        return None, f"judge_error: {e}"


def agent_f1_scores(all_condition_results, scenarios_by_id, use_llm_judge=True):
    """Uses condition 4 (full_system) specialist outputs, scored against
    each scenario's ground-truth risk/opportunity keywords via an LLM
    judge (Groq) -- disclosed here and in every report table as an
    LLM-judge proxy, not a human-verified label.

    Only judges an agent when the scenario's perturbed condition is
    actually within that agent's domain (scenario["relevant_agents"]) --
    e.g. a soil-nitrogen perturbation is only ever scored against
    SoilAgent, never WeatherAgent. Scoring every agent against every
    condition regardless of domain was an earlier version of this
    function and produced misleading near-zero F1 scores for agents that
    were correctly silent about conditions outside their remit; fixed
    here. The negative-control scenario (baseline_normal_rice) is the
    one exception: every agent that ran IS relevant there, since
    correctly reporting "no risk" is exactly what's being checked.

    Every one of the 10 benchmark scenarios carries exactly one ground
    truth signal to detect -- either a risk (8 scenarios) or an
    opportunity (2 scenarios: baseline_normal_rice, market_increasing_
    tomato). An earlier version of this function keyed "is a signal
    expected at all" off ground_truth_risk_keywords alone, so on the 2
    opportunity-only scenarios it treated a CORRECT opportunity
    detection as a false positive (no risk was expected, so any
    detection at all was scored as a false alarm) -- this produced
    misleadingly low F1 for WeatherAgent and MarketAgent specifically.
    Fixed by tracking whether a risk OR an opportunity is expected, and
    scoring detection of whichever one applies as the true positive."""
    full_results = [r for r in all_condition_results if r.get("condition") == "full_system"]
    per_agent = {a: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "judged": 0} for a in
                 ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent"]}
    rows = []

    for r in full_results:
        sid = r["scenario_id"]
        scenario = scenarios_by_id.get(sid)
        if not scenario or r.get("status") != "success":
            continue
        has_risk_kw = bool(scenario["ground_truth_risk_keywords"])
        has_opportunity_kw = bool(scenario["ground_truth_opportunity_keywords"])
        expects_signal = has_risk_kw or has_opportunity_kw
        keywords = scenario["ground_truth_risk_keywords"] or scenario["ground_truth_opportunity_keywords"]
        ##############################################################
        # Describe the OBSERVABLE CONDITION only, never the
        # ground-truth decision it implies. Passing
        # "soil.nitrogen -> Apply Nitrogen Fertilizer" made the judge
        # demand that a *specialist* prescribe the remedy: it scored
        # "agent noted low nitrogen but did not recommend applying
        # nitrogen fertilizer" as a miss, even though detecting the
        # deficiency is the whole of that agent's job and prescribing
        # the fix belongs to the RecommendationAgent. That is what
        # collapsed SoilAgent from F1 0.75 to 0.0 between two runs of
        # substantively identical agent behaviour, and it also made the
        # judge self-inconsistent within a single run.
        ##############################################################
        condition_desc = (
            f"an observable {scenario['perturbed_field']} condition "
            f"in the {scenario['crop']} field"
        )
        relevant_agents = set(scenario.get("relevant_agents", scenario.get("expected_agents", [])))

        for agent_name, out in r.get("specialists", {}).items():
            if agent_name not in per_agent or out.get("status") != "completed":
                continue
            if agent_name not in relevant_agents:
                continue
            if not use_llm_judge:
                continue
            detected, reason = _llm_judge_detected(
                condition_desc, keywords, out.get("analysis"), out.get("risks"), out.get("opportunities"))
            if detected is None:
                continue
            per_agent[agent_name]["judged"] += 1
            if expects_signal and detected:
                per_agent[agent_name]["tp"] += 1
            elif expects_signal and not detected:
                per_agent[agent_name]["fn"] += 1
            elif not expects_signal and detected:
                per_agent[agent_name]["fp"] += 1
            else:
                per_agent[agent_name]["tn"] += 1
            rows.append({"scenario_id": sid, "agent": agent_name, "expects_signal": expects_signal,
                         "detected": detected, "judge_reason": reason})

    scores = {}
    f1_values = []
    for agent, c in per_agent.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else None
        recall = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else None
        accuracy = (c["tp"] + c["tn"]) / c["judged"] if c["judged"] else None
        if not c["judged"]:
            f1 = None
        elif precision and recall and (precision + recall):
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0
        scores[agent] = {
            "n_judged": c["judged"], "tp": c["tp"], "fp": c["fp"], "fn": c["fn"], "tn": c["tn"],
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
        if c["judged"]:
            f1_values.append(f1)

    macro_f1 = round(sum(f1_values) / len(f1_values), 4) if f1_values else None
    return {"metric": "Individual Agent F1-score", "methodology": "LLM-judge (Groq) vs rule-derived ground truth",
            "per_agent": scores, "macro_f1": macro_f1, "rows": rows}


# ==========================================================================
# 5. Recommendation Quality (LLM-judge Likert rubric, NOT human expert)
# ==========================================================================

QUALITY_JUDGE_PROMPT = """You are an agricultural domain reviewer scoring an AI-generated farm recommendation.

FARM SITUATION: crop={crop}, query="{query}"
KEY DATA POINT: {perturbed_field} was deliberately set to an abnormal value to simulate: {ground_truth_decision}
REFERENCE (human-reasonable) RECOMMENDATION: {reference_recommendation}

AI-GENERATED RECOMMENDATION TO SCORE:
{recommendation_text}

Rate the AI-generated recommendation on each dimension using a 1-5 Likert scale
(1=poor, 3=acceptable, 5=excellent), comparing it to the reference recommendation
and the known correct condition:
- agronomic_correctness: is the advice technically sound for this condition?
- relevance: does it actually address the perturbed condition?
- actionability: is it specific and executable, not vague?
- completeness: does it cover what a farmer needs to know/do?
- clarity: is it clearly written?

Return ONLY a JSON object:
{{"agronomic_correctness": 1-5, "relevance": 1-5, "actionability": 1-5, "completeness": 1-5, "clarity": 1-5, "justification": "one sentence"}}
"""

QUALITY_DIMENSIONS = ["agronomic_correctness", "relevance", "actionability", "completeness", "clarity"]


def recommendation_quality(full_system_results, scenarios_by_id):
    from app.utils.groq_client import groq_client
    from app.utils.json_extract import extract_json_object

    per_scenario = []
    for r in full_system_results:
        sid = r["scenario_id"]
        scenario = scenarios_by_id.get(sid)
        if not scenario or r.get("status") != "success":
            continue
        rec_text = safe_get(r, "recommendation", "recommendation") or ""
        prompt = QUALITY_JUDGE_PROMPT.format(
            crop=scenario["crop"], query=scenario["query"], perturbed_field=scenario["perturbed_field"],
            ground_truth_decision=scenario["ground_truth_decision"],
            reference_recommendation=scenario["reference_recommendation"], recommendation_text=rec_text)
        try:
            raw = groq_client.generate(prompt=prompt, temperature=0.0, max_tokens=700)
            scores = extract_json_object(raw, error_label="quality_judge")
            per_scenario.append({"scenario_id": sid, **{d: scores.get(d) for d in QUALITY_DIMENSIONS},
                                 "justification": scores.get("justification")})
        except Exception as e:
            per_scenario.append({"scenario_id": sid, "error": str(e)})

    dimension_stats = {}
    for dim in QUALITY_DIMENSIONS:
        values = [row[dim] for row in per_scenario if isinstance(row.get(dim), (int, float))]
        dimension_stats[dim] = {
            "n": len(values),
            "mean": round(statistics.mean(values), 3) if values else None,
            "std": round(statistics.pstdev(values), 3) if len(values) > 1 else 0.0 if values else None,
        }

    all_scores = [v for row in per_scenario for d in QUALITY_DIMENSIONS
                  for v in [row.get(d)] if isinstance(v, (int, float))]
    overall = {
        "n": len(all_scores),
        "mean": round(statistics.mean(all_scores), 3) if all_scores else None,
        "std": round(statistics.pstdev(all_scores), 3) if len(all_scores) > 1 else 0.0 if all_scores else None,
    }

    return {"metric": "Recommendation Quality", "methodology": "LLM-judge (Groq) 1-5 Likert, NOT a human expert panel",
            "dimensions": dimension_stats, "overall": overall, "rows": per_scenario}


# ==========================================================================
# 6. Hallucination / Error Rate (automated grounding check)
# ==========================================================================

HALLUCINATION_JUDGE_PROMPT = """You are fact-checking an AI-generated agricultural recommendation against the raw sensor/data context it was based on.

RAW DATA CONTEXT (ground truth for what was actually observed):
{raw_context_json}

AI-GENERATED TEXT TO CHECK:
{generated_text}

Does the AI-generated text contain any of the following?
- A specific numeric claim (e.g. a temperature, NDVI, price) that contradicts the raw data context
- A claim about a data source that was actually unavailable/failed
- A fabricated fact not supported by the raw data context or general agronomic knowledge
- An internal contradiction

Return ONLY a JSON object:
{{"has_error": true or false, "error_type": "numeric_contradiction|fabricated_evidence|unsupported_claim|contradiction|none", "explanation": "one short sentence"}}
"""


def hallucination_rate(full_system_results, scenarios_by_id):
    from app.utils.groq_client import groq_client
    from app.utils.json_extract import extract_json_object

    rows = []
    for r in full_system_results:
        sid = r["scenario_id"]
        scenario = scenarios_by_id.get(sid)
        if not scenario or r.get("status") != "success":
            continue
        raw_context = {
            "weather": safe_get(r, "context", "weather", "raw_data"),
            "soil": safe_get(r, "context", "soil", "soil"),
            "satellite": {"vegetation": safe_get(r, "context", "satellite", "vegetation"),
                          "water": safe_get(r, "context", "satellite", "water")},
            "market_trend": safe_get(r, "context", "market", "assessment", "trend"),
        }
        generated_text = " ".join(filter(None, [
            safe_get(r, "recommendation", "recommendation"),
            safe_get(r, "executive", "decision"),
        ]))
        prompt = HALLUCINATION_JUDGE_PROMPT.format(
            raw_context_json=json.dumps(raw_context, default=str), generated_text=generated_text[:1500])
        try:
            raw = groq_client.generate(prompt=prompt, temperature=0.0, max_tokens=700)
            result = extract_json_object(raw, error_label="hallucination_judge")
            rows.append({"scenario_id": sid, "has_error": bool(result.get("has_error")),
                        "error_type": result.get("error_type"), "explanation": result.get("explanation")})
        except Exception as e:
            rows.append({"scenario_id": sid, "judge_error": str(e)})

    judged = [row for row in rows if "has_error" in row]
    n = len(judged)
    errors = sum(1 for row in judged if row["has_error"])
    rate = round(100 * errors / n, 2) if n else None
    lo, hi = wilson_ci(errors, n) if n else (0, 0)
    return {"metric": "Hallucination / Error Rate", "methodology": "Automated LLM-judge grounding check vs raw context",
            "n": n, "errors": errors, "value_pct": rate,
            "ci_95": [round(lo * 100, 2), round(hi * 100, 2)] if n else None, "rows": rows}


# ==========================================================================
# 7. Trust Calibration
# ==========================================================================

def trust_calibration(full_system_results):
    per_agent_outcomes = {}
    per_agent_trust = {}
    for r in full_system_results:
        if r.get("status") != "success":
            continue
        for agent_name, out in r.get("specialists", {}).items():
            per_agent_outcomes.setdefault(agent_name, []).append(out.get("status") == "completed")
            trust_mean = safe_get(out, "governance", "posterior_mean")
            if trust_mean is not None:
                per_agent_trust.setdefault(agent_name, []).append(trust_mean)

    rows = []
    abs_errors = []
    for agent_name in sorted(set(per_agent_outcomes) | set(per_agent_trust)):
        outcomes = per_agent_outcomes.get(agent_name, [])
        trusts = per_agent_trust.get(agent_name, [])
        observed_reliability = round(sum(outcomes) / len(outcomes), 4) if outcomes else None
        trust_mean = round(sum(trusts) / len(trusts), 4) if trusts else None
        error = round(abs(observed_reliability - trust_mean), 4) if observed_reliability is not None and trust_mean is not None else None
        if error is not None:
            abs_errors.append(error)
        rows.append({"agent": agent_name, "n": len(outcomes), "trust_mean": trust_mean,
                     "observed_reliability": observed_reliability, "abs_calibration_error": error})

    mace = round(sum(abs_errors) / len(abs_errors), 4) if abs_errors else None
    return {"metric": "Trust Calibration", "rows": rows, "mean_abs_calibration_error": mace}


# ==========================================================================
# 8. Latency
# ==========================================================================

def _stats(values):
    if not values:
        return {"n": 0, "mean": None, "median": None, "std": None, "p95": None, "p99": None}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "std": round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0,
        "p95": round(percentile(values, 95), 2),
        "p99": round(percentile(values, 99), 2),
    }


def latency_stats(full_system_results):
    """Only total end-to-end latency and per-specialist/executive
    execution_time are instrumented by the pipeline (raw result
    stage_times contains only {"total": ...} -- planner, collaborative
    reasoning, and recommendation stages have no separate timestamp in
    the pipeline's own output). Rather than silently drop those three
    stages, they are reported explicitly as unavailable (n=0, all
    stats None) so a reader cannot mistake their absence for a zero
    latency -- see the "never fabricate / distinguish unavailable
    metrics" requirement this evaluation framework was built against."""
    total_times = [r["total_time"] for r in full_system_results if r.get("status") == "success" and r.get("total_time") is not None]

    per_stage_agent = {}
    for r in full_system_results:
        if r.get("status") != "success":
            continue
        for agent_name, out in r.get("specialists", {}).items():
            t = out.get("execution_time")
            if t is not None:
                per_stage_agent.setdefault(agent_name, []).append(t)
        exec_time = safe_get(r, "executive", "execution_time")
        if exec_time is not None:
            per_stage_agent.setdefault("ExecutiveAgent", []).append(exec_time)

    return {
        "metric": "Latency", "total_pipeline": _stats(total_times),
        "per_agent": {k: _stats(v) for k, v in per_stage_agent.items()},
        "planner": _stats([]),
        "collaborative_reasoning": _stats([]),
        "recommendation": _stats([]),
        "unavailable_stages_note": "Planner, collaborative reasoning, and recommendation stage latency are not "
                                    "separately instrumented by the current AgriMind pipeline (only total_time "
                                    "and per-specialist/executive execution_time are recorded in the raw result "
                                    "object) -- reported here as unavailable (N=0) rather than omitted or fabricated.",
    }


# ==========================================================================
# Driver
# ==========================================================================

def load_results(results_dir):
    all_results = []
    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(results_dir, fname), "r", encoding="utf-8") as f:
            record = json.load(f)
        all_results.append(record)
    return all_results


def load_scenarios():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset", "benchmark_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["scenario_id"]: s for s in data["scenarios"]}, data
