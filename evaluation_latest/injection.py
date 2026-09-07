"""
==========================================================================
AgriMind Research-Grade Evaluation — Data Injection Harness

Ground truth for this evaluation is constructed by taking REAL collected
context (pulled from evaluation/data/raw/*.json, i.e. genuine Open-Meteo /
SoilGrids-derived synthetic / Sentinel-2 / market-CSV output already
collected by AgriMind during the earlier baseline evaluation) and applying
a single, explicit, documented field perturbation per benchmark scenario,
so that the resulting ground-truth risk/opportunity/decision label is
unambiguous and independently checkable against the crop profile's own
numeric thresholds -- not invented, not hand-waved.

This module patches the five collector singletons imported by
app.collectors.data_collector so that, for the duration of one evaluation
run, they return a FIXED synthetic reading instead of making a live call.
Everything downstream (planner, specialist agents, reasoning, executive,
recommendation, explanation, TRUSTAI) is the real, unmodified AgriMind
code running on that fixed input.
==========================================================================
"""

import copy
import os
import sys

EVAL_LATEST_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(EVAL_LATEST_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.chdir(PROJECT_ROOT)


class CollectorPatch:
    """
    Context manager: while active, the five collector singletons return
    fixed synthetic data instead of calling their real (live-API /
    synthetic-CSV / SQLite) sources. Restores the originals on exit
    unconditionally, including on exception.
    """

    def __init__(self, fixture):
        """
        fixture: dict with keys weather, soil, satellite, market,
        historical -- each the exact dict a real collector.collect()
        would return (see dataset/build_dataset.py for how these are
        constructed).
        """
        self.fixture = fixture
        self._originals = {}

    def __enter__(self):
        from app.collectors.weather_collector import weather_collector
        from app.collectors.soil_collector import soil_collector
        from app.collectors.satellite_collector import satellite_collector
        from app.collectors.market_collector import market_collector
        from app.collectors.historical_collector import historical_collector

        targets = {
            "weather": weather_collector,
            "soil": soil_collector,
            "satellite": satellite_collector,
            "market": market_collector,
            "historical": historical_collector,
        }

        for key, singleton in targets.items():
            self._originals[key] = singleton.collect
            fixed_value = copy.deepcopy(self.fixture[key])
            singleton.collect = (lambda v: (lambda *a, **k: copy.deepcopy(v)))(fixed_value)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from app.collectors.weather_collector import weather_collector
        from app.collectors.soil_collector import soil_collector
        from app.collectors.satellite_collector import satellite_collector
        from app.collectors.market_collector import market_collector
        from app.collectors.historical_collector import historical_collector

        targets = {
            "weather": weather_collector,
            "soil": soil_collector,
            "satellite": satellite_collector,
            "market": market_collector,
            "historical": historical_collector,
        }
        for key, singleton in targets.items():
            if key in self._originals:
                singleton.collect = self._originals[key]
        return False
