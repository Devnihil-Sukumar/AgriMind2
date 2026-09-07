"""
==========================================================================
AgriMind Research-Grade Evaluation -- Controlled Latency Study

Addresses a confound in the headline latency numbers.

In normal operation the specialists are deliberately split across
providers: Weather and Soil run a 4B model on a local CPU, while
Satellite, Market and Historical run a 120B model on hosted
accelerators. That split is a sensible deployment choice, but it makes
the per-agent latency bars uninterpretable as architecture: the observed
~4x gap between Soil (278s) and Satellite (60s) measures CPU inference
versus hosted inference, not any property of those agents.

This script measures each specialist twice on an identical fixture:

  condition MIXED    -- production routing (Weather/Soil local CPU)
  condition UNIFORM  -- AGRIMIND_FORCE_PROVIDER=ollama, every agent on the
                        same local tier

The UNIFORM column is the one that can be read architecturally. The
difference between the columns quantifies the hardware artefact that
must be subtracted from the production figures before any structural
claim is made.

It deliberately does NOT run the full pipeline: collaborative reasoning
contributes nothing to per-agent specialist latency, and excluding it
keeps this script scoped to the specialists.

NOTE: the project has since moved to an Ollama-only deployment (see
app/utils/provider_config.py DEFAULT_PROVIDERS), so MIXED and UNIFORM
now both route through the same local model and the "artefact" this
script measures is expected to be ~0 by construction. It is kept for
the historical mixed-provider comparison and as a regression check
that routing is in fact now uniform.

Usage
-----
    venv/Scripts/python.exe evaluation_latest/latency_study.py --repeats 2

Author : AgriMind Team
==========================================================================
"""

import argparse
import json
import os
import statistics
import sys
import time

EVAL_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_ROOT)

import injection  # noqa: E402  (sets sys.path / cwd / encoding)

RESULTS_PATH = os.path.join(EVAL_ROOT, "results", "latency_study.json")

AGENTS = ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent"]


def build_context(scenario):
    """Reuse the benchmark's own context builder so the agents see
    exactly what they see during a benchmark run."""
    import baselines
    return baselines._build_pipeline_context(scenario)


def time_agent(agent, context):
    start = time.time()
    try:
        out = agent.execute(context)
        status = out.get("status", "completed")
    except Exception as error:  # noqa: BLE001
        status = f"error: {type(error).__name__}"
    return round(time.time() - start, 2), status


def run_condition(force_provider, scenario, repeats):
    """Fresh interpreter state per condition: the provider override is
    read at import time, so the agent modules must be re-imported for a
    changed setting to take effect."""

    if force_provider:
        os.environ["AGRIMIND_FORCE_PROVIDER"] = force_provider
    else:
        os.environ.pop("AGRIMIND_FORCE_PROVIDER", None)

    for mod in [m for m in list(sys.modules) if m.startswith("app.agents")]:
        del sys.modules[mod]

    from app.agents.weather_agent import weather_agent
    from app.agents.soil_agent import soil_agent
    from app.agents.satellite_agent import satellite_agent
    from app.agents.market_agent import market_agent

    registry = {
        "WeatherAgent": weather_agent,
        "SoilAgent": soil_agent,
        "SatelliteAgent": satellite_agent,
        "MarketAgent": market_agent,
    }

    timings = {a: [] for a in AGENTS}
    statuses = {a: [] for a in AGENTS}

    with injection.CollectorPatch(scenario["fixture"]):
        context = build_context(scenario)

        for r in range(repeats):
            for name in AGENTS:
                agent = registry[name]
                provider = agent.get_llm_provider()
                elapsed, status = time_agent(agent, context)
                timings[name].append(elapsed)
                statuses[name].append(status)
                print(f"   [{force_provider or 'mixed':7s}] rep{r + 1} "
                      f"{name:16s} provider={provider:7s} "
                      f"{elapsed:7.2f}s  {status}", flush=True)

    return timings, statuses


def summarise(timings):
    out = {}
    for name, vals in timings.items():
        clean = [v for v in vals if v is not None]
        out[name] = {
            "n": len(clean),
            "mean": round(statistics.mean(clean), 2) if clean else None,
            "min": round(min(clean), 2) if clean else None,
            "max": round(max(clean), 2) if clean else None,
        }
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Measure per-agent latency under mixed vs uniform providers."
    )
    parser.add_argument("--repeats", type=int, default=2,
                        help="Timed repetitions per agent per condition.")
    parser.add_argument("--scenario", default=None,
                        help="Benchmark scenario id to use (default: first).")
    args = parser.parse_args()

    with open(os.path.join(EVAL_ROOT, "dataset", "benchmark_queries.json"),
              encoding="utf-8") as f:
        scenarios = json.load(f)["scenarios"]

    scenario = (
        next(s for s in scenarios if s["scenario_id"] == args.scenario)
        if args.scenario else scenarios[0]
    )

    print(f"Scenario: {scenario['scenario_id']}  ({scenario['crop']})")
    print(f"Repeats : {args.repeats} per agent per condition")
    print()

    print("Condition UNIFORM (all agents forced to ollama)")
    uniform_t, uniform_s = run_condition("ollama", scenario, args.repeats)

    print()
    print("Condition MIXED (production routing)")
    mixed_t, mixed_s = run_condition(None, scenario, args.repeats)

    result = {
        "scenario_id": scenario["scenario_id"],
        "repeats": args.repeats,
        "uniform_ollama": summarise(uniform_t),
        "mixed_production": summarise(mixed_t),
        "note":
            "UNIFORM holds hardware constant and is the column that may be "
            "read architecturally. MIXED reflects production routing, in "
            "which Weather/Soil run a small model on local CPU. The "
            "difference is a hardware artefact, not an architectural "
            "property.",
        "statuses": {"uniform": uniform_s, "mixed": mixed_s},
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print()
    print("=" * 62)
    print(f"{'agent':17s} {'uniform(ollama)':>15s} {'mixed(prod)':>13s} {'artefact':>10s}")
    print("=" * 62)
    for name in AGENTS:
        u = result["uniform_ollama"][name]["mean"]
        m = result["mixed_production"][name]["mean"]
        art = f"{m - u:+.2f}s" if (u is not None and m is not None) else "--"
        print(f"{name:17s} {str(u) + 's':>15s} {str(m) + 's':>13s} {art:>10s}")
    print("=" * 62)
    print(f"written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
