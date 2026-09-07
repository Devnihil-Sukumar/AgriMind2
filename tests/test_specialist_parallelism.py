"""
==========================================================================
AgriMind

Specialist Parallelism Regression Tests

Specialists were changed from a sequential loop to concurrent execution
(executor.execute_specialists). The properties that change had to
preserve are easy to break silently later, so they are pinned here:

1. Parallel and sequential paths return the SAME agents with the SAME
   statuses.
2. Output order follows the execution plan, not completion order --
   downstream stages and the evaluation harness read this dict and must
   see a stable ordering regardless of which agent finishes first.
3. Later-stage agents (Recommendation/Executive) and unknown agents are
   still filtered out.
4. A failing specialist is isolated: it is recorded as failed without
   taking down the other specialists (the graceful-degradation property
   the evaluation reports).
5. Parallel execution is actually faster than sequential for
   independent agents.

These use stub agents, so they run in milliseconds and make no LLM
calls.

Run:
    venv/Scripts/python.exe -m pytest tests/test_specialist_parallelism.py -v

Author : AgriMind Team
==========================================================================
"""

import os
import sys
import time

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import app.orchestrator.executor as executor_module  # noqa: E402


##########################################################################
# Stubs
##########################################################################

class StubAgent:

    def __init__(self, name, delay=0.05, fail=False):

        self.name = name
        self.delay = delay
        self.fail = fail

    def execute(self, context):

        time.sleep(self.delay)

        if self.fail:
            raise RuntimeError(f"{self.name} exploded")

        return {
            "status": "completed",
            "analysis": f"{self.name} analysis",
            "confidence": 0.8
        }


class _StubDecision:
    action = "auto_execute"
    rationale = "stubbed"


class _StubPrecheck:
    decision = _StubDecision()


class StubTrustAI:

    def review(self, agent_name):
        return _StubPrecheck()

    def record_outcome(self, agent_name, result):
        return {"agent": agent_name}


##########################################################################
# Fixtures
##########################################################################

@pytest.fixture
def executor(monkeypatch):
    """A DynamicExecutor wired to stub agents and stubbed governance, so
    these tests exercise concurrency rather than TRUSTAI or the LLMs."""

    monkeypatch.setattr(executor_module, "trustai", StubTrustAI())
    monkeypatch.setattr(executor_module, "asdict", lambda x: {"stub": True})

    ex = executor_module.DynamicExecutor()

    ex.agent_registry = {
        "WeatherAgent": StubAgent("WeatherAgent", 0.20),
        "SoilAgent": StubAgent("SoilAgent", 0.30),
        "SatelliteAgent": StubAgent("SatelliteAgent", 0.05),
        "MarketAgent": StubAgent("MarketAgent", 0.10),
        "HistoricalAgent": StubAgent("HistoricalAgent", 0.05),
    }

    return ex


def plan_for(*agents):
    return (
        [{"agent": a, "priority": i + 1} for i, a in enumerate(agents)]
        + [{"agent": "RecommendationAgent", "priority": len(agents) + 1}]
    )


def run(ex, monkeypatch, plan, parallel):

    monkeypatch.setattr(
        executor_module,
        "PARALLEL_SPECIALISTS",
        parallel
    )

    return ex.execute_specialists(plan, {})


##########################################################################
# Tests
##########################################################################

def test_parallel_and_sequential_agree(executor, monkeypatch):
    """Same agents, same statuses, whichever path runs."""

    plan = plan_for("WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent")

    sequential = run(executor, monkeypatch, plan, parallel=False)
    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert set(sequential) == set(parallel)

    assert (
        {k: v["status"] for k, v in sequential.items()}
        == {k: v["status"] for k, v in parallel.items()}
    )


def test_output_order_follows_plan_not_completion(executor, monkeypatch):
    """SatelliteAgent finishes first but must not appear first: the dict
    is rebuilt in plan order so downstream consumers see a stable
    sequence."""

    plan = plan_for("WeatherAgent", "SoilAgent", "SatelliteAgent")

    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert list(parallel.keys()) == [
        "WeatherAgent",
        "SoilAgent",
        "SatelliteAgent"
    ]


def test_later_stage_and_unknown_agents_are_filtered(executor, monkeypatch):

    plan = plan_for("WeatherAgent", "NotARealAgent")
    plan.append({"agent": "ExecutiveAgent", "priority": 9})

    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert list(parallel.keys()) == ["WeatherAgent"]
    assert "RecommendationAgent" not in parallel
    assert "ExecutiveAgent" not in parallel
    assert "NotARealAgent" not in parallel


def test_one_failing_specialist_does_not_sink_the_others(executor, monkeypatch):
    """Per-agent exception isolation is the graceful-degradation property
    the evaluation reports; concurrency must not have weakened it."""

    executor.agent_registry["SoilAgent"] = StubAgent(
        "SoilAgent",
        0.05,
        fail=True
    )

    plan = plan_for("WeatherAgent", "SoilAgent", "SatelliteAgent")

    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert parallel["SoilAgent"]["status"] == "failed"
    assert "exploded" in parallel["SoilAgent"]["error"]

    assert parallel["WeatherAgent"]["status"] == "completed"
    assert parallel["SatelliteAgent"]["status"] == "completed"


def test_parallel_is_faster_than_sequential(executor, monkeypatch):

    plan = plan_for("WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent")

    start = time.time()
    run(executor, monkeypatch, plan, parallel=False)
    sequential_seconds = time.time() - start

    start = time.time()
    run(executor, monkeypatch, plan, parallel=True)
    parallel_seconds = time.time() - start

    ##################################################################
    # Sequential pays 0.20+0.30+0.05+0.10 = 0.65s; parallel should pay
    # about the slowest single agent (0.30s). A 1.5x floor keeps this
    # from flaking on a loaded CI machine while still failing loudly if
    # the work silently goes back to running one-at-a-time.
    ##################################################################

    assert parallel_seconds < sequential_seconds
    assert sequential_seconds / parallel_seconds > 1.5


def test_single_agent_plan_skips_the_thread_pool(executor, monkeypatch):
    """One planned agent takes the direct path -- no pool, same result."""

    plan = plan_for("WeatherAgent")

    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert list(parallel.keys()) == ["WeatherAgent"]
    assert parallel["WeatherAgent"]["status"] == "completed"


def test_per_agent_execution_time_is_individual_not_cumulative(executor, monkeypatch):
    """Each agent times only its own work, so the latency metrics stay
    meaningful under concurrency."""

    plan = plan_for("WeatherAgent", "SoilAgent", "SatelliteAgent")

    parallel = run(executor, monkeypatch, plan, parallel=True)

    assert parallel["SatelliteAgent"]["execution_time"] < 0.2
    assert parallel["SoilAgent"]["execution_time"] >= 0.3
