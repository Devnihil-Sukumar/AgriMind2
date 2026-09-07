"""
==========================================================================
AgriMind

NLI Contradiction Detection Tests

The NLI check is the second LLM-free grounding instrument. Its whole
value rests on distinguishing an ASSERTION about the current state
(which can contradict a sensor reading) from an INSTRUCTION or TARGET
(which legitimately names a different value).

That distinction is not academic. An earlier version flagged

    "Re-sample soil pH 10-14 days after the first lime application and
     adjust the second dose to reach the target pH 5.5-6.5."

as contradicting "The soil pH is 3.2." at 0.972 confidence. The system
was right -- it was prescribing lime to raise pH from 3.2 toward the
5.5-6.5 target -- and the checker was wrong. Left unfixed it would have
reported correct treatment plans as hallucinations, inflating the error
rate exactly on the scenarios the system handled best.

Tests requiring the NLI model are skipped when it is not cached, so the
suite still runs offline; the filtering logic is tested unconditionally.

Run:
    venv/Scripts/python.exe -m pytest tests/test_nli_check.py -v

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

import nli_check as N  # noqa: E402


##########################################################################
# Prescriptive filter -- no model needed
##########################################################################

@pytest.mark.parametrize("sentence", [
    "Re-sample soil pH 10-14 days after the first lime application to reach the target pH 5.5-6.5.",
    "Apply a nitrogen fertiliser at the recommended rate.",
    "Monitor soil moisture daily for the next week.",
    "Irrigate the field immediately to relieve water stress.",
    "Maintain pH within the target range of 5.5 to 6.5.",
])
def test_prescriptive_sentences_are_excluded(sentence):
    """Instructions and targets are not claims about present state."""
    assert N.is_prescriptive(sentence) is True


@pytest.mark.parametrize("sentence", [
    "The soil pH is 3.2, which is strongly acidic.",
    "Soil nitrogen is Low for this crop.",
    "The crop shows high water stress in the satellite imagery.",
])
def test_factual_assertions_are_kept(sentence):
    assert N.is_prescriptive(sentence) is False


def test_split_claims_drops_prescriptive_but_keeps_assertions():
    text = ("The soil pH is 3.2, which is strongly acidic. "
            "Apply agricultural lime before sowing. "
            "Soil nitrogen is Low for this crop.")
    claims = N.split_claims(text)
    assert len(claims) == 2
    assert all("lime" not in c for c in claims)


##########################################################################
# Premise construction -- no model needed
##########################################################################

def test_premises_are_built_mechanically_from_context():
    """Premises must come from the context dictionary, never be authored
    per scenario, so the check cannot be tuned to flatter the system."""
    context = {
        "soil": {"soil": {"ph": 6.2, "nitrogen": "Low"}},
        "satellite": {"vegetation": {"ndvi": 0.8}, "water": {"stress": "High"}},
        "market": {"assessment": {"trend": "Increasing"}},
    }
    premises = N.build_premises(context)
    joined = " ".join(premises)

    assert "6.2" in joined
    assert "Low" in joined
    assert "0.8" in joined
    assert "High" in joined
    assert "Increasing" in joined


def test_empty_context_yields_no_premises():
    assert N.build_premises({}) == []


def test_topic_gating_pairs_only_related_statements():
    assert N.shares_topic("The soil pH is 6.2.", "Soil pH is far too low.") is True
    assert N.shares_topic("The soil pH is 6.2.", "Market prices are rising.") is False


##########################################################################
# Model-backed behaviour -- skipped when the model is unavailable
##########################################################################

def _model_available():
    try:
        N._get_pipeline()
        return True
    except Exception:  # noqa: BLE001
        return False


requires_model = pytest.mark.skipif(
    not _model_available(),
    reason="NLI model not cached locally",
)


@requires_model
def test_direct_numeric_contradiction_is_detected():
    out = N.check_run(
        {"soil": {"soil": {"ph": 6.2}}},
        "The soil pH is 3.1, which is severely acidic.",
    )
    assert len(out["contradictions"]) >= 1


@requires_model
def test_faithful_restatement_is_not_flagged():
    out = N.check_run(
        {"soil": {"soil": {"ph": 6.2}}},
        "The soil pH is 6.2, which sits within the acceptable band.",
    )
    assert out["contradictions"] == []


@requires_model
def test_treatment_target_is_not_flagged_as_contradiction():
    """The regression this module exists to prevent."""
    out = N.check_run(
        {"soil": {"soil": {"ph": 3.2}}},
        "Re-sample soil pH 10-14 days after liming and adjust the dose to "
        "reach the target pH 5.5-6.5.",
    )
    assert out["contradictions"] == []
