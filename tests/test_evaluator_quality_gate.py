"""
==========================================================================
AgriMind

Evaluator Quality-Gate Regression Tests

AgriMind degrades gracefully: when an LLM provider is unavailable the
pipeline falls back to deterministic paths and still returns
status="success". That is correct in production and dangerous in
evaluation -- a benchmark run starved of Groq quota looks complete while
actually measuring fallback behaviour.

This was observed live during the 50-scenario run: with the daily token
quota exhausted, `vegetation_critical_yield_rice` came back
status="success" with generation_mode="deterministic_fallback",
confidence 0.35 and a failed SoilAgent. The evaluator's checkpointing
would have cached that as "done" and it would have silently entered the
published metrics.

evaluator.is_degraded() closes that hole, so these tests pin it.

Run:
    venv/Scripts/python.exe -m pytest tests/test_evaluator_quality_gate.py -v

Author : AgriMind Team
==========================================================================
"""

import json
import os
import sys

import pytest

EVAL_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evaluation_latest"
)
sys.path.insert(0, EVAL_ROOT)

import evaluator as E  # noqa: E402


def record(mode="llm", specialist_status="completed", status="success", reasoning="Real Gemini consensus text."):
    return {
        "status": status,
        "recommendation": {"generation_mode": mode, "confidence": 0.83},
        "specialists": {"WeatherAgent": {"status": specialist_status}},
        "reasoning": reasoning,
    }


##########################################################################
# is_degraded
##########################################################################

def test_clean_llm_run_is_not_degraded():
    assert E.is_degraded(record()) is False


def test_deterministic_fallback_is_degraded():
    """The exact shape seen when Groq's daily quota ran out."""
    assert E.is_degraded(record(mode="deterministic_fallback")) is True


def test_failed_specialist_is_degraded():
    assert E.is_degraded(record(specialist_status="failed")) is True


def test_rejected_specialist_is_degraded():
    """A TRUSTAI rejection means that agent never ran, so the run is not
    a complete measurement either."""
    assert E.is_degraded(record(specialist_status="rejected")) is True


def test_unavailable_specialist_is_not_degraded():
    """"unavailable" means the agent ran correctly and its data source
    genuinely had nothing -- a real result, not a degraded one."""
    assert E.is_degraded(record(specialist_status="unavailable")) is False


def test_gemini_reasoning_fallback_is_degraded():
    """Gemini's free tier caps at 20 requests/day -- far tighter than
    Groq's ~200k-token budget -- so this is the failure mode most
    likely to recur. It is invisible in recommendation.generation_mode
    and in every specialist's own status, since only the collaborative-
    reasoning STAGE degrades; 12 of 15 banked results were silently
    contaminated this way before this check existed."""
    fallback_reasoning = (
        "Deterministic consensus generated because Gemini reasoning "
        "was unavailable."
    )
    assert E.is_degraded(record(reasoning=fallback_reasoning)) is True


def test_reasoning_mentioning_deterministic_elsewhere_is_not_flagged():
    """The check is a specific phrase match, not a substring ban on the
    word "deterministic" -- real Gemini output could legitimately
    describe conditions as deterministic without having fallen back."""
    real_text = "Soil conditions are the deterministic factor limiting yield here."
    assert E.is_degraded(record(reasoning=real_text)) is False


##########################################################################
# already_done -- the checkpointing contract
##########################################################################

@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "RAW_DIR", str(tmp_path))
    return tmp_path


def write(raw_dir, scenario_id, payload):
    path = raw_dir / f"{scenario_id}__full_system.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_clean_run_counts_as_done(raw_dir):
    write(raw_dir, "clean", record())
    assert E.already_done("clean", "full_system") is True


def test_degraded_run_is_retried_not_cached(raw_dir):
    """The whole point: a quota-starved run must NOT be treated as
    complete, so a later resume re-runs it with real quota."""
    write(raw_dir, "degraded", record(mode="deterministic_fallback"))
    assert E.already_done("degraded", "full_system") is False


def test_errored_run_is_retried(raw_dir):
    write(raw_dir, "errored", record(status="error"))
    assert E.already_done("errored", "full_system") is False


def test_missing_run_is_not_done(raw_dir):
    assert E.already_done("never_ran", "full_system") is False


def test_corrupt_file_is_retried_rather_than_crashing(raw_dir):
    (raw_dir / "corrupt__full_system.json").write_text("{not json", encoding="utf-8")
    assert E.already_done("corrupt", "full_system") is False
