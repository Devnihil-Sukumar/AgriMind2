"""
==========================================================================
AgriMind

Live Data Source Regression Tests

Soil moved from a synthetic CSV to ISRIC SoilGrids, and market from a
synthetic CSV to Agmarknet (data.gov.in). Both are real networked
services that can be slow, rate-limited, or simply have no data for a
location, so the properties worth pinning are about the FALLBACK
contract rather than about any particular measured value:

  * a coverage gap or an outage must never fail the stage
  * the output schema must be identical either way, so downstream
    agents cannot accidentally depend on which path ran
  * provenance must be reported honestly (live_source / metadata.source)
  * unit conversions must stay correct -- the sand/clay/silt triple
    summing to 100% is the check that caught a real off-by-10x bug
  * a trend must never be invented from a single observation

These use stubs and offline fixtures, so they make no network calls and
run in milliseconds.

Run:
    venv/Scripts/python.exe -m pytest tests/test_live_data_sources.py -v

Author : AgriMind Team
==========================================================================
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from app.services.soilgrids_service import SoilGridsService  # noqa: E402
from app.services.agmarknet_service import AgmarknetService  # noqa: E402


##########################################################################
# SoilGrids -- unit conversion
##########################################################################

def soilgrids_payload(values):
    """Build a SoilGrids-shaped response from {property: raw_int}."""
    return {
        "properties": {
            "layers": [
                {
                    "name": name,
                    "depths": [
                        {"label": "0-5cm", "values": {"mean": raw}}
                    ],
                }
                for name, raw in values.items()
            ]
        }
    }


# Raw integers captured from a real response at (10.85, 77.05).
REAL_RAW = {
    "phh2o": 74,
    "nitrogen": 241,
    "soc": 266,
    "sand": 482,
    "clay": 267,
    "silt": 251,
    "cec": 235,
    "bdod": 144,
}


def test_texture_fractions_sum_to_100_percent():
    """The check that caught a real 10x conversion error: sand, clay and
    silt are a partition of the soil and must total ~100%."""

    parsed = SoilGridsService()._parse(
        soilgrids_payload(REAL_RAW), 10.85, 77.05
    )

    total = (
        parsed["sand_percent"]
        + parsed["clay_percent"]
        + parsed["silt_percent"]
    )

    assert total == pytest.approx(100.0, abs=0.5)


def test_conversions_match_the_documented_contract():

    parsed = SoilGridsService()._parse(
        soilgrids_payload(REAL_RAW), 10.85, 77.05
    )

    assert parsed["ph"] == pytest.approx(7.4)
    assert parsed["sand_percent"] == pytest.approx(48.2)
    assert parsed["clay_percent"] == pytest.approx(26.7)
    assert parsed["cec"] == pytest.approx(23.5)
    assert parsed["bulk_density"] == pytest.approx(1.44)
    # g/kg -> percent for the two AgriMind classifies in percent
    assert parsed["nitrogen_percent"] == pytest.approx(0.241)
    assert parsed["organic_carbon_percent"] == pytest.approx(2.66)
    assert parsed["live_source"] is True


def test_values_land_in_agronomically_plausible_ranges():

    parsed = SoilGridsService()._parse(
        soilgrids_payload(REAL_RAW), 10.85, 77.05
    )

    assert 3.0 < parsed["ph"] < 10.0
    assert 0.0 < parsed["nitrogen_percent"] < 1.0
    assert 1.0 < parsed["cec"] < 60.0
    assert 0.9 < parsed["bulk_density"] < 1.9
    assert 0.0 < parsed["wilting_point"] < parsed["field_capacity"] < 1.0


def test_coverage_gap_returns_none_rather_than_inventing_values():
    """Built-up land yields null means; the service must say "no data"
    so the tool can fall back, not fabricate a soil profile."""

    nulls = {name: None for name in REAL_RAW}

    assert SoilGridsService()._parse(
        soilgrids_payload(nulls), 11.0168, 76.9558
    ) is None


def test_partial_response_missing_ph_is_treated_as_a_gap():

    partial = dict(REAL_RAW)
    partial["phh2o"] = None
    partial["clay"] = None

    assert SoilGridsService()._parse(
        soilgrids_payload(partial), 10.85, 77.05
    ) is None


##########################################################################
# Agmarknet -- trend derivation
##########################################################################

@pytest.fixture
def agmarknet(tmp_path, monkeypatch):
    """A service writing its price history to a temp file, so tests never
    touch the real data/market_price_history.json."""

    monkeypatch.setattr(
        "app.services.agmarknet_service.PRICE_HISTORY_PATH",
        str(tmp_path / "history.json")
    )

    return AgmarknetService()


def test_first_observation_reports_unknown_not_a_guess(agmarknet):
    """A single snapshot carries no trend information. Inventing one
    would put a fabricated signal behind a sell/hold recommendation."""

    assert agmarknet.derive_trend("Erode Mandi", "rice", 2000.0) == "Unknown"


def test_trend_follows_direction_of_change(agmarknet):

    agmarknet.derive_trend("Erode Mandi", "rice", 2000.0)

    assert agmarknet.derive_trend("Erode Mandi", "rice", 2200.0) == "Increasing"
    assert agmarknet.derive_trend("Erode Mandi", "rice", 1900.0) == "Decreasing"


def test_small_fluctuation_is_stable_not_a_trend(agmarknet):
    """Day-to-day mandi noise of a percent or two is not a trend."""

    agmarknet.derive_trend("Salem Mandi", "wheat", 2000.0)

    assert agmarknet.derive_trend("Salem Mandi", "wheat", 2010.0) == "Stable"


def test_history_is_kept_per_market_and_commodity(agmarknet):
    """Two markets must not contaminate each other's trend."""

    agmarknet.derive_trend("Salem Mandi", "rice", 2000.0)
    agmarknet.derive_trend("Erode Mandi", "rice", 5000.0)

    # Salem rising judged against Salem's own 2000, not Erode's 5000.
    assert agmarknet.derive_trend("Salem Mandi", "rice", 2200.0) == "Increasing"


def test_normalise_maps_onto_market_tool_column_names(agmarknet):
    """Live rows must be drop-in compatible with the ranker, which reads
    the CSV's capitalised column names."""

    rows = agmarknet._normalise(
        [{
            "state": "Tamil Nadu",
            "district": "Erode",
            "market": "Erode Mandi",
            "min_price": "2100",
            "max_price": "2500",
            "modal_price": "2300",
            "arrival_date": "04/09/2026",
        }],
        "rice"
    )

    assert rows is not None
    row = rows[0]

    for column in (
        "State", "District", "Crop", "Market",
        "Min_Price", "Max_Price", "Modal_Price",
        "Trend", "Last_Updated"
    ):
        assert column in row

    assert row["Modal_Price"] == 2300.0
    assert row["live_source"] is True


def test_unparseable_rows_are_dropped_not_zero_filled(agmarknet):

    rows = agmarknet._normalise(
        [
            {"market": "Bad", "modal_price": "not-a-number"},
            {"market": "AlsoBad", "modal_price": "0"},
        ],
        "rice"
    )

    assert rows is None


##########################################################################
# Agmarknet -- circuit breaker
##########################################################################

def test_breaker_opens_after_repeated_failures_and_short_circuits(agmarknet):
    """data.gov.in has extended outages. Without the breaker every run
    pays retries x timeout (~135s) before falling back to a dataset it
    was going to use anyway."""

    import time as _time
    import app.services.agmarknet_service as module

    assert agmarknet.circuit_open is False

    for _ in range(module.FAILURE_THRESHOLD):
        agmarknet._record_failure()

    assert agmarknet.circuit_open is True

    started = _time.time()
    result = agmarknet.fetch_prices("rice")
    elapsed = _time.time() - started

    assert result is None
    # Must return immediately rather than attempting the dead endpoint.
    assert elapsed < 1.0


def test_success_closes_the_breaker(agmarknet):

    import app.services.agmarknet_service as module

    for _ in range(module.FAILURE_THRESHOLD):
        agmarknet._record_failure()

    assert agmarknet.circuit_open is True

    agmarknet._record_success()

    assert agmarknet.circuit_open is False


def test_empty_result_set_does_not_trip_the_breaker(agmarknet, monkeypatch):
    """A reachable API with no rows for this crop is a healthy response.
    Treating it as a failure would disable live prices for 15 minutes
    because someone asked about an uncommon commodity."""

    class _Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"records": []}

    monkeypatch.setattr(
        "app.services.agmarknet_service.requests.get",
        lambda *a, **k: _Response()
    )

    assert agmarknet.fetch_prices("dragonfruit") is None
    assert agmarknet.circuit_open is False
