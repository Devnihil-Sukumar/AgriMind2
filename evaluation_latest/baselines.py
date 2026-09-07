"""
==========================================================================
AgriMind Research-Grade Evaluation — Ablation Condition Runners

Four conditions, run on identical synthetic-fixture input (via
injection.CollectorPatch), each reusing the REAL, unmodified AgriMind
agent/reasoning/executive/recommendation code -- only the amount of
architecture wired together differs:

  1. single_agent      -- one specialist only, no fusion, no TRUSTAI
  2. multi_no_reasoning -- all planned specialists, deterministic merge
                           instead of collaborative_engine, no TRUSTAI
  3. multi_with_reasoning -- all planned specialists, REAL Gemini
                             collaborative reasoning, no TRUSTAI
  4. full_system       -- the actual, unmodified dynamic_orchestrator.run()
                           (specialists + real reasoning + TRUSTAI)

Conditions 1-3 bypass TRUSTAI simply by calling agents directly instead
of going through app.orchestrator.executor's TRUSTAI-wrapped path.
Condition 4 is the real system end to end, unchanged.

Specialist concurrency is held CONSTANT across conditions. Condition 4
runs specialists concurrently because the real executor does, so
conditions 2-3 must too: otherwise the ablation's latency column would
be comparing execution strategy (sequential vs concurrent) rather than
the architectural feature each condition actually ablates, and the full
system would look faster purely because it was the only one allowed to
overlap its agents. Condition 1 runs a single specialist, so
concurrency does not apply to it either way.
==========================================================================
"""

import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import injection  # noqa: E402  (sets up sys.path / cwd / encoding)

##########################################################################
# Mirrors app.orchestrator.executor's default worker count so the
# baselines overlap specialists exactly as the real pipeline does.
##########################################################################

MAX_SPECIALIST_WORKERS = 5


def _time_call(fn, *args, **kwargs):
    start = time.time()
    result = fn(*args, **kwargs)
    return result, round(time.time() - start, 3)


def _specialist_singletons():
    from app.agents.weather_agent import weather_agent
    from app.agents.soil_agent import soil_agent
    from app.agents.satellite_agent import satellite_agent
    from app.agents.market_agent import market_agent
    from app.agents.historical_agent import historical_agent
    return {
        "WeatherAgent": weather_agent,
        "SoilAgent": soil_agent,
        "SatelliteAgent": satellite_agent,
        "MarketAgent": market_agent,
        "HistoricalAgent": historical_agent,
    }


def _merge_reasoning(specialist_outputs):
    """Deterministic stand-in for collaborative_engine: union risks and
    opportunities, average confidence. No conflict detection, no
    consensus building, no LLM call -- this IS "multi-agent without
    collaborative reasoning"."""
    from app.reasoning.reasoning_output import CollaborativeReasoning

    risks, opportunities, confidences = [], [], []
    for out in specialist_outputs.values():
        risks.extend(out.get("risks", []) or [])
        opportunities.extend(out.get("opportunities", []) or [])
        confidences.append(float(out.get("confidence", 0) or 0))

    merged_risks = list(dict.fromkeys(risks))
    merged_opportunities = list(dict.fromkeys(opportunities))
    confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    return CollaborativeReasoning(
        summary=f"Deterministic merge of {len(specialist_outputs)} specialist outputs (no collaborative reasoning).",
        consensus="N/A -- collaborative reasoning stage skipped for this condition.",
        merged_risks=merged_risks,
        merged_opportunities=merged_opportunities,
        conflicts=[],
        confidence=confidence,
        evidence=[],
        metadata={"agents": list(specialist_outputs.keys()), "agent_count": len(specialist_outputs),
                  "llm_provider": "none (deterministic merge)"},
    )


def _build_pipeline_context(scenario):
    from app.agents.crop_knowledge_agent import crop_knowledge_agent
    from app.collectors.data_collector import data_collector
    from app.agents.context_agent import context_agent

    crop_result = crop_knowledge_agent.execute(scenario["crop"])
    crop_profile = crop_result["crop_profile"]
    collected = data_collector.collect(
        crop_profile=crop_profile,
        latitude=scenario["latitude"],
        longitude=scenario["longitude"],
    )
    context = context_agent.analyze(collected)
    return context


def _finalize(context, reasoning, executive, recommendation, specialists, stage_times, condition):
    return {
        "status": "success",
        "error": None,
        "context": context,
        "specialists": specialists,
        "reasoning": reasoning.__dict__ if hasattr(reasoning, "__dict__") else reasoning,
        "executive": executive,
        "recommendation": recommendation,
        "stage_times": stage_times,
        "condition": condition,
        "governance_used": condition == "full_system",
    }


def run_single_agent(scenario):
    """Condition 1: exactly one specialist (the first in expected_agents),
    no fusion stage, no TRUSTAI."""
    stage_times = {}
    try:
        with injection.CollectorPatch(scenario["fixture"]):
            context, t_ctx = _time_call(_build_pipeline_context, scenario)
            stage_times["context_build"] = t_ctx

            agent_name = scenario["expected_agents"][0]
            agent = _specialist_singletons()[agent_name]

            out, t_agent = _time_call(agent.execute, context)
            stage_times[agent_name] = t_agent
            specialists = {agent_name: out}

            reasoning = _merge_reasoning(specialists)

            from app.executive.executive_agent import executive_agent
            executive, t_exec = _time_call(executive_agent.execute, context, reasoning)
            stage_times["executive"] = t_exec

            from app.agents.recommendation_agent import recommendation_agent
            recommendation, t_rec = _time_call(recommendation_agent.execute, context, reasoning, executive)
            stage_times["recommendation"] = t_rec

        return _finalize(context, reasoning, executive, recommendation, specialists, stage_times, "single_agent")
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                "condition": "single_agent", "stage_times": stage_times}


def _run_multi(scenario, use_real_reasoning, condition_name):
    stage_times = {}
    try:
        with injection.CollectorPatch(scenario["fixture"]):
            context, t_ctx = _time_call(_build_pipeline_context, scenario)
            stage_times["context_build"] = t_ctx

            from app.orchestrator.planner import planner
            plan, t_plan = _time_call(planner.plan, scenario["query"], context)
            stage_times["planner"] = t_plan

            agent_names = [
                step["agent"] for step in plan.get("execution_plan", [])
                if step["agent"] not in ("RecommendationAgent", "ExecutiveAgent")
            ]
            singletons = _specialist_singletons()
            runnable = [name for name in agent_names if name in singletons]

            ##########################################################
            # Concurrent, to match the real executor (see module
            # docstring). Each agent is still timed individually, and
            # results are rebuilt in plan order so the recorded
            # specialist ordering matches the sequential path exactly.
            ##########################################################

            def _run(name):
                return _time_call(singletons[name].execute, context)

            if len(runnable) <= 1:
                timed = {name: _run(name) for name in runnable}
            else:
                with ThreadPoolExecutor(
                    max_workers=min(len(runnable), MAX_SPECIALIST_WORKERS),
                    thread_name_prefix="baseline-specialist"
                ) as pool:
                    timed = dict(zip(runnable, pool.map(_run, runnable)))

            specialists = {}
            for name in runnable:
                out, t_agent = timed[name]
                stage_times[name] = t_agent
                specialists[name] = out

            successful = {k: v for k, v in specialists.items() if v.get("status") == "completed"}

            if use_real_reasoning:
                from app.reasoning.collaborative_engine import collaborative_engine
                reasoning, t_reason = _time_call(
                    collaborative_engine.collaborative_reasoning, context, successful or specialists)
                stage_times["reasoning"] = t_reason
            else:
                reasoning = _merge_reasoning(successful or specialists)
                stage_times["reasoning"] = 0.0

            from app.executive.executive_agent import executive_agent
            executive, t_exec = _time_call(executive_agent.execute, context, reasoning)
            stage_times["executive"] = t_exec

            from app.agents.recommendation_agent import recommendation_agent
            recommendation, t_rec = _time_call(recommendation_agent.execute, context, reasoning, executive)
            stage_times["recommendation"] = t_rec

        return _finalize(context, reasoning, executive, recommendation, specialists, stage_times, condition_name)
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                "condition": condition_name, "stage_times": stage_times}


def run_multi_no_reasoning(scenario):
    """Condition 2: real planner + real specialists, deterministic merge
    instead of collaborative_engine, no TRUSTAI."""
    return _run_multi(scenario, use_real_reasoning=False, condition_name="multi_no_reasoning")


def run_multi_with_reasoning(scenario):
    """Condition 3: real planner + real specialists + REAL Gemini
    collaborative reasoning, no TRUSTAI."""
    return _run_multi(scenario, use_real_reasoning=True, condition_name="multi_with_reasoning")


def run_full_system(scenario):
    """Condition 4: the actual, unmodified AgriMind pipeline end to end,
    including TRUSTAI governance."""
    try:
        with injection.CollectorPatch(scenario["fixture"]):
            from app.orchestrator.dynamic_orchestrator import dynamic_orchestrator
            start = time.time()
            result = dynamic_orchestrator.run(
                user_query=scenario["query"],
                crop=scenario["crop"],
                latitude=scenario["latitude"],
                longitude=scenario["longitude"],
            )
            elapsed = round(time.time() - start, 3)

        execution = result.get("execution", {})
        return {
            "status": "success",
            "error": None,
            "context": result.get("context"),
            "specialists": execution.get("specialists", {}),
            "reasoning": execution.get("reasoning"),
            "executive": execution.get("executive"),
            "recommendation": execution.get("recommendation"),
            "explanation": execution.get("explanation"),
            "governance": execution.get("governance"),
            "statistics": execution.get("statistics"),
            "plan": result.get("plan"),
            "total_time": elapsed,
            "stage_times": {"total": elapsed},
            "condition": "full_system",
            "governance_used": True,
            "raw_result": result,
        }
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                "condition": "full_system", "stage_times": {}}


CONDITIONS = {
    "single_agent": run_single_agent,
    "multi_no_reasoning": run_multi_no_reasoning,
    "multi_with_reasoning": run_multi_with_reasoning,
    "full_system": run_full_system,
}
