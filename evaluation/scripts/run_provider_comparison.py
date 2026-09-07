"""
Ollama vs Groq provider comparison.

Isolates the LLM-provider variable: for a fixed set of real farm
contexts, sends each Ollama-routed specialist's exact prompt to BOTH
providers (Ollama qwen3:4b locally, Groq openai/gpt-oss-120b in the
cloud) and records latency + first-try JSON validity for each. Much
cheaper than re-running the full pipeline per provider, and isolates
the variable actually being compared.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness_utils import (  # noqa: E402
    PROVIDER_DIR, log_event, already_done, result_path, dump_json,
    to_jsonable,
)

DEFAULT_LAT = 11.0168
DEFAULT_LON = 76.9558

CONTEXTS = [
    {"crop": "rice", "query": "What should I do to maximize rice yield this season?"},
    {"crop": "cotton", "query": "Is cotton suitable to grow in this location right now, and what are the risks?"},
    {"crop": "wheat", "query": "Is it a good time to irrigate my wheat field?"},
]


def build_context(crop):
    from app.agents.crop_knowledge_agent import crop_knowledge_agent
    from app.collectors.data_collector import data_collector
    from app.agents.context_agent import context_agent

    crop_profile = crop_knowledge_agent.execute(crop)["crop_profile"]
    collected = data_collector.collect(
        crop_profile=crop_profile, latitude=DEFAULT_LAT, longitude=DEFAULT_LON
    )
    return context_agent.analyze(collected)


def try_provider(client_call, prompt, max_tokens=None):
    from app.utils.json_extract import extract_json_substring

    start = time.time()
    try:
        kwargs = {"prompt": prompt}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        raw = client_call(**kwargs)
        elapsed = time.time() - start
        try:
            extract_json_substring(raw, error_label="eval")
            valid_json = True
            json_error = None
        except ValueError as e:
            valid_json = False
            json_error = str(e)
        return {
            "elapsed_seconds": round(elapsed, 3),
            "valid_json_first_try": valid_json,
            "json_error": json_error,
            "response_chars": len(raw or ""),
            "raw_response": raw,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "elapsed_seconds": round(elapsed, 3),
            "valid_json_first_try": False,
            "json_error": None,
            "response_chars": 0,
            "raw_response": None,
            "error": f"{type(e).__name__}: {e}",
        }


def main():
    from app.agents.weather_agent import weather_agent
    from app.agents.soil_agent import soil_agent
    from app.agents.satellite_agent import satellite_agent
    from app.agents.historical_agent import historical_agent
    from app.utils.ollama_client import ollama_client
    from app.utils.groq_client import groq_client

    agents = {
        "WeatherAgent": weather_agent,
        "SoilAgent": soil_agent,
        "SatelliteAgent": satellite_agent,
        "HistoricalAgent": historical_agent,
    }

    for ctx_spec in CONTEXTS:
        crop = ctx_spec["crop"]
        ctx_run_id = f"context_{crop}"

        log_event({"phase": "provider_comparison", "run_id": ctx_run_id,
                    "status": "building_context"})
        context = build_context(crop)

        for agent_name, agent in agents.items():
            run_id = f"{crop}_{agent_name}"
            if already_done(PROVIDER_DIR, run_id):
                log_event({"phase": "provider_comparison", "run_id": run_id,
                            "status": "skipped_cached"})
                continue

            if not agent.is_source_available(context):
                log_event({"phase": "provider_comparison", "run_id": run_id,
                            "status": "skipped_unavailable"})
                continue

            prompt = agent.build_prompt(context)

            log_event({"phase": "provider_comparison", "run_id": run_id,
                        "status": "started"})

            ollama_result = try_provider(ollama_client.generate, prompt)
            groq_result = try_provider(
                groq_client.generate, prompt, max_tokens=ollama_client.num_predict
            )

            record = {
                "run_id": run_id,
                "crop": crop,
                "agent": agent_name,
                "prompt_chars": len(prompt),
                "ollama": ollama_result,
                "groq": groq_result,
            }
            dump_json(to_jsonable(record), result_path(PROVIDER_DIR, run_id))

            log_event({"phase": "provider_comparison", "run_id": run_id,
                        "status": "completed",
                        "note": f"ollama={ollama_result['elapsed_seconds']}s "
                                f"groq={groq_result['elapsed_seconds']}s"})

    log_event({"phase": "provider_comparison", "run_id": "-", "status": "phase_complete"})


if __name__ == "__main__":
    main()
