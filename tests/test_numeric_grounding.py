"""
==========================================================================
AgriMind

Deterministic Numeric Grounding Tests

The grounding check exists to corroborate the LLM-judged hallucination
rate with a measurement that has no model in the loop. Its value depends
entirely on not manufacturing false positives: agronomic advice is full
of legitimate numbers that are not readings ("recheck in 3-5 days",
"apply at 2-3 week intervals", numbered action lists), and an early
version of this check counted several of them as hallucinations because
a measurement cue happened to appear nearby in the same sentence.

These tests pin the exclusions that fix that, plus the matching
arithmetic.

Run:
    venv/Scripts/python.exe -m pytest tests/test_numeric_grounding.py -v

Author : AgriMind Team
==========================================================================
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "evaluation_latest",
    ),
)

import grounding as G  # noqa: E402


def values(text):
    return {c["value"] for c in G.extract_measurement_claims(text)}


##########################################################################
# Claims that SHOULD be extracted
##########################################################################

def test_extracts_cued_measurements():
    assert values("Soil pH is 6.2 and NDVI reads 0.80.") == {6.2, 0.80}


def test_extracts_price_claims():
    assert 2450.0 in values("Modal price is Rs.2450 per quintal.")


##########################################################################
# Claims that must NOT be extracted (false-positive guards)
##########################################################################

def test_day_horizon_is_not_a_measurement():
    """The failure that motivated the exclusion list: 'pH' earlier in the
    sentence was validating '3-5 days' as a reading."""
    assert values("Soil pH is 6.2. Recheck in 3-5 days.") == {6.2}


def test_week_interval_is_not_a_measurement():
    assert values("Apply nitrogen at 2-3 week intervals; soil pH measured 5.4.") == {5.4}


def test_numbered_list_marker_is_not_a_measurement():
    """Observed in real output: '...moisture daily. 7. Record harvest
    quantity' -- the '7.' is a step number, not a reading."""
    text = "Monitor soil moisture daily. 7. Record harvest quantity."
    assert 7.0 not in values(text)


def test_uncued_bare_number_is_ignored():
    """No measurement cue nearby means the check stays silent rather than
    guessing."""
    assert values("Contact the extension officer at counter 12.") == set()


##########################################################################
# Grounding arithmetic
##########################################################################

def test_value_within_tolerance_is_grounded():
    assert G.is_grounded(6.2, [6.21]) is True


def test_percentage_matches_stored_fraction():
    """Context stores field capacity as 0.32; text may render it as 32%."""
    assert G.is_grounded(32.0, [0.32]) is True


def test_absent_value_is_ungrounded():
    assert G.is_grounded(99.9, [6.21, 0.80]) is False


##########################################################################
# Aggregation
##########################################################################

def test_run_with_fabricated_reading_is_flagged():
    run = {
        "status": "success",
        "scenario_id": "s1",
        "context": {"soil": {"soil": {"ph": 6.2}}},
        "recommendation": {"recommendation": "Soil pH is 9.9, apply lime."},
        "executive": {"decision": "Field Inspection"},
    }
    out = G.numeric_grounding([run])
    assert out["total_ungrounded_claims"] == 1
    assert out["ungrounded_run_rate_pct"] == 100.0


def test_run_with_only_grounded_readings_is_clean():
    run = {
        "status": "success",
        "scenario_id": "s2",
        "context": {"soil": {"soil": {"ph": 6.2}}},
        "recommendation": {"recommendation": "Soil pH is 6.2, within range."},
        "executive": {"decision": "Continue Monitoring"},
    }
    out = G.numeric_grounding([run])
    assert out["total_ungrounded_claims"] == 0
    assert out["ungrounded_run_rate_pct"] == 0.0


def test_failed_runs_are_excluded_from_the_denominator():
    runs = [
        {"status": "error", "scenario_id": "bad"},
        {"status": "success", "scenario_id": "ok",
         "context": {}, "recommendation": {"recommendation": "No readings."},
         "executive": {"decision": "Continue Monitoring"}},
    ]
    assert G.numeric_grounding(runs)["n_runs"] == 1
