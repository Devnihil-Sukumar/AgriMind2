"""
==========================================================================
AgriMind Research-Grade Evaluation — Benchmark Dataset Construction

METHODOLOGY (read this before trusting any ground-truth label below):

Ground truth in this benchmark is NOT human-expert-authored and NOT
independently sourced. It is constructed as follows, and every scenario
below documents its own derivation explicitly:

  1. Start from a REAL context AgriMind itself collected during the
     earlier baseline evaluation (evaluation/data/raw/*.json) -- genuine
     Open-Meteo weather, synthetic-CSV soil/market data, and real
     Sentinel-2 satellite indices for a specific crop and location.
  2. Apply ONE explicit, documented perturbation to a single field (e.g.
     force soil pH to 3.2), chosen so that it unambiguously crosses a
     threshold already present in that crop's own profile
     (crop_profile.optimal_conditions / satellite_thresholds / soil
     preferences -- see app/knowledge/crop_profile_validator.py's
     DEFAULT_SCHEMA for the canonical field set).
  3. The ground-truth risk/decision is whatever that crossed threshold
     implies, expressed using AgriMind's OWN executive-decision
     vocabulary (see app/executive/executive_engine.py's infer_decision,
     which is a closed set: Immediate Irrigation, Field Inspection, Apply
     Nitrogen Fertilizer, Apply Organic Manure, Prepare for Harvest and
     Selling, Continue Monitoring). This is a real, load-bearing finding
     documented in the final report, not an evaluation convenience: the
     system cannot express a decision outside this 6-item set no matter
     how the input is perturbed, and this benchmark is necessarily
     constructed within that constraint to remain fair.

This is a controlled, single-variable, reproducible benchmark analogous
to a fixture-based test suite -- not a field survey and not a substitute
for human agronomist validation. That limitation is stated in every
report this benchmark feeds.
==========================================================================
"""

import copy
import json
import os

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(DATASET_DIR))
RAW_BASELINE_DIR = os.path.join(PROJECT_ROOT, "evaluation", "data", "raw")

DEFAULT_LAT = 11.0168
DEFAULT_LON = 76.9558

# Which real completed baseline run to clone context from, per crop.
BASE_RUN_BY_CROP = {
    "rice": "rice_yield_r1.json",
    "cotton": "cotton_yield_r1.json",
    "wheat": "wheat_yield_r1.json",
    "mango": "mango_yield_r1.json",
    "tomato": "tomato_yield_r1.json",
}

# Crops added to extend the benchmark past its original 50-scenario grid.
# No AgriMind pipeline run was ever captured for these two, so there is no
# real context to clone under BASE_RUN_BY_CROP. Instead they reuse the
# real Open-Meteo / Sentinel-2 / soil sensor context captured for RICE at
# the same DEFAULT_LAT/DEFAULT_LON -- those readings are location-bound,
# not crop-bound, so they are genuinely real data at this location, not
# fabricated. The only crop-specific input is the crop_profile (optimal
# ranges, satellite thresholds) that the perturbation and ground-truth
# logic reads, which is loaded directly from AgriMind's own cached
# canonical profile for that crop.
EXTRA_CROP_TEMPLATE_RAW = "rice_yield_r1.json"
EXTRA_CROPS = ["apple", "orange"]
CROP_PROFILES_DIR = os.path.join(PROJECT_ROOT, "app", "knowledge", "crop_profiles")

# Query-type -> the specialist agents this benchmark treats as "expected".
# This is our own explicit, documented definition (domain-reasonable
# query-intent -> specialist mapping), used as the routing-accuracy
# ground truth. It is deliberately NOT derived from AgriMind's own
# planner, to avoid circularity.
EXPECTED_AGENTS_BY_QUERY_TYPE = {
    "yield": ["WeatherAgent", "SoilAgent", "SatelliteAgent"],
    "irrigation": ["WeatherAgent", "SoilAgent", "SatelliteAgent"],
    "suitability": ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent"],
    "market": ["MarketAgent", "HistoricalAgent"],
}

VALID_DECISIONS = [
    "Immediate Irrigation",
    "Field Inspection",
    "Apply Nitrogen Fertilizer",
    "Apply Organic Manure",
    "Prepare for Harvest and Selling",
    "Continue Monitoring",
]


def _load_base_context(crop):
    if crop in BASE_RUN_BY_CROP:
        path = os.path.join(RAW_BASELINE_DIR, BASE_RUN_BY_CROP[crop])
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return copy.deepcopy(data["result"]["context"]), copy.deepcopy(data["result"]["crop_profile"])

    # Extended crop (see EXTRA_CROPS docstring above): real sensor
    # context borrowed from rice's captured run at the same location,
    # paired with this crop's own cached canonical profile.
    path = os.path.join(RAW_BASELINE_DIR, EXTRA_CROP_TEMPLATE_RAW)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    context = copy.deepcopy(data["result"]["context"])

    profile_path = os.path.join(CROP_PROFILES_DIR, f"{crop}.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        crop_profile = json.load(f)

    return context, crop_profile


def _fixture_from_context(context):
    """The five sections of a real context are exactly what each
    collector.collect() returned (context_agent passes them through
    unchanged), so they can be replayed directly via CollectorPatch."""
    return {
        "weather": context["weather"],
        "soil": context["soil"],
        "satellite": context["satellite"],
        "market": context["market"],
        "historical": context["historical"],
    }


def _neutralize(fixture, crop_profile):
    """
    Reset a cloned fixture to a low-risk baseline BEFORE applying a
    scenario's specific perturbation, so each scenario tests exactly one
    variable instead of inheriting whatever risks happened to be present
    in the real run it was cloned from.
    """
    opt = crop_profile.get("optimal_conditions", {})
    f = copy.deepcopy(fixture)

    temp_mid = (opt.get("temperature", {}).get("minimum", 20) + opt.get("temperature", {}).get("maximum", 30)) / 2
    hum_mid = (opt.get("humidity", {}).get("minimum", 60) + opt.get("humidity", {}).get("maximum", 80)) / 2
    rain_mid = (opt.get("rainfall", {}).get("minimum", 1000) + opt.get("rainfall", {}).get("maximum", 2000)) / 2 / 100
    ph_mid = (opt.get("soil_ph", {}).get("minimum", 5.5) + opt.get("soil_ph", {}).get("maximum", 6.5)) / 2

    f["weather"]["raw_data"]["temperature"] = temp_mid
    f["weather"]["raw_data"]["humidity"] = hum_mid
    f["weather"]["raw_data"]["rainfall"] = rain_mid
    f["weather"]["raw_data"]["wind_speed"] = 10.0
    f["weather"]["status"] = "success"
    f["weather"]["assessment"] = {"crop": crop_profile.get("crop"), "status": "Good",
                                   "identified_risks": [], "opportunities": ["Weather conditions are favorable."]}

    f["soil"]["soil"]["ph"] = ph_mid
    f["soil"]["raw_data"]["ph"] = ph_mid
    f["soil"]["soil"]["nitrogen"] = crop_profile.get("soil", {}).get("preferred_nitrogen", "High")
    f["soil"]["raw_data"]["nitrogen"] = crop_profile.get("soil", {}).get("preferred_nitrogen", "High")
    f["soil"]["soil"]["organic_carbon"] = crop_profile.get("soil", {}).get("preferred_organic_carbon", "Medium")
    f["soil"]["raw_data"]["organic_carbon"] = crop_profile.get("soil", {}).get("preferred_organic_carbon", "Medium")
    f["soil"]["assessment"] = {
        "soil_health_score": 92, "ph_status": "Optimal", "nitrogen_status": "Optimal",
        "organic_carbon_status": "Optimal", "texture": "Loam", "risks": [],
        "opportunities": ["Soil pH is within the optimal range."],
    }

    thresh = crop_profile.get("satellite_thresholds", {})
    f["satellite"]["vegetation"]["ndvi"] = thresh.get("ndvi", {}).get("excellent", 0.8)
    f["satellite"]["vegetation"]["health"] = "Excellent"
    f["satellite"]["water"]["ndwi"] = thresh.get("ndwi", {}).get("low_stress", 0.4)
    f["satellite"]["water"]["stress"] = "Low"
    f["satellite"]["soil"]["exposure"] = "Low"
    f["satellite"]["status"] = "success"
    f["satellite"]["assessment"] = {"vegetation_score": 90, "recommendation": "Continue normal management."}

    f["market"]["assessment"]["trend"] = "Stable"
    for m in f["market"].get("top_markets", []) or []:
        m["trend"] = "Stable"

    f["historical"]["status"] = "success"
    f["historical"]["record_count"] = 0

    return f


def _perturb_soil_ph(fixture, crop_profile, direction):
    opt = crop_profile["optimal_conditions"]["soil_ph"]
    value = opt["minimum"] - 2.3 if direction == "low" else opt["maximum"] + 2.0
    fixture["soil"]["soil"]["ph"] = round(value, 2)
    fixture["soil"]["raw_data"]["ph"] = round(value, 2)
    fixture["soil"]["assessment"]["ph_status"] = "Below optimal" if direction == "low" else "Above optimal"
    fixture["soil"]["assessment"]["risks"] = [
        f"Soil pH ({value:.2f}) is {'below' if direction == 'low' else 'above'} the optimal range "
        f"({opt['minimum']}-{opt['maximum']})."
    ]
    return fixture


def _perturb_nitrogen_low(fixture, crop_profile):
    fixture["soil"]["soil"]["nitrogen"] = "Low"
    fixture["soil"]["raw_data"]["nitrogen"] = "Low"
    fixture["soil"]["assessment"]["nitrogen_status"] = "Low"
    fixture["soil"]["assessment"]["risks"] = [
        "Soil nitrogen level is Low, below the crop's preferred "
        f"{crop_profile.get('soil', {}).get('preferred_nitrogen', 'High')} requirement."
    ]
    return fixture


def _perturb_organic_carbon_low(fixture, crop_profile):
    fixture["soil"]["soil"]["organic_carbon"] = "Low"
    fixture["soil"]["raw_data"]["organic_carbon"] = "Low"
    fixture["soil"]["assessment"]["organic_carbon_status"] = "Low"
    fixture["soil"]["assessment"]["risks"] = ["Organic carbon is below crop requirement."]
    return fixture


def _perturb_water_stress(fixture, crop_profile):
    thresh = crop_profile["satellite_thresholds"]["ndwi"]
    value = thresh["high_stress"] - 0.35
    fixture["satellite"]["water"]["ndwi"] = round(value, 3)
    fixture["satellite"]["water"]["stress"] = "High"
    fixture["weather"]["raw_data"]["rainfall"] = 0.0
    fixture["weather"]["assessment"]["identified_risks"] = ["Rainfall below optimal, no recent precipitation."]
    fixture["satellite"]["assessment"]["recommendation"] = "Increase irrigation immediately."
    return fixture


def _perturb_vegetation_critical(fixture, crop_profile):
    thresh = crop_profile["satellite_thresholds"]["ndvi"]
    value = thresh["poor"] - 0.15
    fixture["satellite"]["vegetation"]["ndvi"] = round(value, 3)
    fixture["satellite"]["vegetation"]["health"] = "Critical"
    fixture["satellite"]["assessment"]["recommendation"] = "Inspect crop for disease or nutrient deficiency."
    return fixture


def _perturb_market_increasing(fixture):
    fixture["market"]["assessment"]["trend"] = "Increasing"
    for m in fixture["market"].get("top_markets", []) or []:
        m["trend"] = "Increasing"
    fixture["market"]["assessment"]["opportunities"] = ["Market prices are trending upward across top markets."]
    return fixture


##########################################################################
# Compound perturbations
#
# Every scenario above changes exactly one field, so passing it only
# proves the system reacts to a single signal in isolation. These
# perturb TWO fields from different specialists' domains at once, so the
# ground-truth decision requires infer_decision()'s actual priority
# order (water stress > vegetation > nitrogen > organic carbon > market,
# per app/executive/executive_engine.py) to resolve correctly -- a
# distractor signal is present and must be correctly subordinated, not
# just a single signal correctly detected.
##########################################################################

def _perturb_compound_water_market(fixture, crop_profile):
    fixture = _perturb_water_stress(fixture, crop_profile)
    fixture = _perturb_market_increasing(fixture)
    return fixture


def _perturb_compound_nitrogen_market(fixture, crop_profile):
    fixture = _perturb_nitrogen_low(fixture, crop_profile)
    fixture = _perturb_market_increasing(fixture)
    return fixture


def _perturb_compound_organic_market(fixture, crop_profile):
    fixture = _perturb_organic_carbon_low(fixture, crop_profile)
    fixture = _perturb_market_increasing(fixture)
    return fixture


def _perturb_compound_vegetation_nitrogen(fixture, crop_profile):
    fixture = _perturb_vegetation_critical(fixture, crop_profile)
    fixture = _perturb_nitrogen_low(fixture, crop_profile)
    return fixture


def _perturb_compound_nitrogen_organic(fixture, crop_profile):
    fixture = _perturb_nitrogen_low(fixture, crop_profile)
    fixture = _perturb_organic_carbon_low(fixture, crop_profile)
    return fixture


##########################################################################
# Query phrasings
#
# Each query type carries several natural phrasings rather than one
# fixed sentence, rotated across crops. With a single phrasing per type
# the planner can score well by pattern-matching one sentence instead of
# reading intent, which would make Routing Accuracy look better than the
# system deserves. Rotation is deterministic (index by crop position) so
# the dataset stays reproducible.
##########################################################################

QUERY_PHRASINGS = {
    "irrigation": [
        "Is it a good time to irrigate my {crop} field?",
        "Does my {crop} need watering right now, or can it wait?",
        "My {crop} field looks dry -- should I irrigate this week?",
    ],
    "yield": [
        "What should I do to maximize {crop} yield this season?",
        "How can I get a better harvest from my {crop} crop?",
        "What is holding back my {crop} yield, and how do I fix it?",
    ],
    "suitability": [
        "Is {crop} suitable to grow in this location right now, and what are the risks?",
        "Would {crop} be a good crop to plant on this land?",
        "Should I go ahead with {crop} here, or is something working against it?",
    ],
    "market": [
        "Is now a good time to sell my {crop} harvest?",
        "Should I sell my {crop} now or hold for a better price?",
        "Where and when should I sell my {crop} for the best return?",
    ],
}

CROPS = ["rice", "cotton", "wheat", "mango", "tomato", "apple", "orange"]


def _phrasing(query_type, crop, variant):
    options = QUERY_PHRASINGS[query_type]
    return options[variant % len(options)].format(crop=crop)


def build_scenarios():
    scenarios = []

    def make(scenario_id, crop, query_type, query, perturb_fn, gt_decision,
             gt_risk_keywords, gt_opportunity_keywords, perturbed_field, relevant_agents,
             probes_known_limitation=False):
        context, crop_profile = _load_base_context(crop)
        fixture = _fixture_from_context(context)
        fixture = _neutralize(fixture, crop_profile)
        fixture = perturb_fn(fixture, crop_profile) if perturb_fn.__code__.co_argcount > 1 else perturb_fn(fixture)

        scenarios.append({
            "scenario_id": scenario_id,
            "crop": crop,
            "query_type": query_type,
            "query": query,
            "latitude": DEFAULT_LAT,
            "longitude": DEFAULT_LON,
            "perturbed_field": perturbed_field,
            "expected_agents": EXPECTED_AGENTS_BY_QUERY_TYPE[query_type],
            # Which specialist(s) the perturbed condition actually falls
            # within the domain of -- e.g. a soil-nitrogen perturbation is
            # SoilAgent's to catch, not WeatherAgent's. Agent F1 (metrics.py)
            # only judges an agent's risk/opportunity detection against a
            # condition when that agent appears here (or for the negative-
            # control scenario, where every agent correctly reporting "no
            # risk" is itself the thing being checked).
            "relevant_agents": relevant_agents,
            "ground_truth_decision": gt_decision,
            "ground_truth_risk_keywords": gt_risk_keywords,
            "ground_truth_opportunity_keywords": gt_opportunity_keywords,
            "reference_recommendation": REFERENCE_RECOMMENDATIONS[gt_decision],
            # True for scenarios that deliberately probe a documented gap
            # in AgriMind's closed decision vocabulary (soil pH has no
            # dedicated decision output). These are EXPECTED to fail
            # Decision Accuracy; the flag lets the report separate a real
            # capability gap from ordinary error instead of silently
            # depressing the headline number.
            "probes_known_limitation": probes_known_limitation,
            "fixture": fixture,
        })

    ##################################################################
    # Systematic grid: every perturbation type x every crop, with
    # query phrasing rotated per crop. Replaces the original ten
    # hand-written scenarios, which covered only 10 of the available
    # crop x query-type x perturbation combinations and left
    # Decision/Routing/Hallucination accuracy resting on N=10 with
    # confidence intervals far too wide to conclude from.
    ##################################################################

    for i, crop in enumerate(CROPS):

        # ---- Immediate Irrigation (irrigation framing) ----
        make(f"water_stress_irrigation_{crop}", crop, "irrigation",
             _phrasing("irrigation", crop, i),
             _perturb_water_stress, "Immediate Irrigation",
             ["water stress", "drought", "irrigation", "rainfall"], [],
             "satellite.water.ndwi, weather.raw_data.rainfall",
             ["SatelliteAgent", "WeatherAgent"])

        # ---- Immediate Irrigation (suitability framing) ----
        make(f"water_stress_suitability_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i),
             _perturb_water_stress, "Immediate Irrigation",
             ["water stress", "drought", "irrigation", "rainfall"], [],
             "satellite.water.ndwi, weather.raw_data.rainfall",
             ["SatelliteAgent", "WeatherAgent"])

        # ---- Field Inspection (yield framing) ----
        make(f"vegetation_critical_yield_{crop}", crop, "yield",
             _phrasing("yield", crop, i),
             _perturb_vegetation_critical, "Field Inspection",
             ["vegetation", "crop health", "ndvi", "critical"], [],
             "satellite.vegetation.ndvi",
             ["SatelliteAgent"])

        # ---- Field Inspection (suitability framing) ----
        make(f"vegetation_critical_suitability_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i + 1),
             _perturb_vegetation_critical, "Field Inspection",
             ["vegetation", "crop health", "ndvi", "critical"], [],
             "satellite.vegetation.ndvi",
             ["SatelliteAgent"])

        # ---- Apply Nitrogen Fertilizer (yield framing) ----
        make(f"nitrogen_low_yield_{crop}", crop, "yield",
             _phrasing("yield", crop, i + 1),
             _perturb_nitrogen_low, "Apply Nitrogen Fertilizer",
             ["nitrogen", "fertilizer", "nutrient deficiency"], [],
             "soil.nitrogen",
             ["SoilAgent"])

        # ---- Apply Nitrogen Fertilizer (suitability framing) ----
        make(f"nitrogen_low_suitability_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i + 2),
             _perturb_nitrogen_low, "Apply Nitrogen Fertilizer",
             ["nitrogen", "fertilizer", "nutrient deficiency"], [],
             "soil.nitrogen",
             ["SoilAgent"])

        # ---- Apply Organic Manure ----
        make(f"organic_carbon_low_{crop}", crop, "yield",
             _phrasing("yield", crop, i + 2),
             _perturb_organic_carbon_low, "Apply Organic Manure",
             ["organic carbon", "organic matter", "manure", "compost"], [],
             "soil.organic_carbon",
             ["SoilAgent"])

        # ---- Prepare for Harvest and Selling ----
        make(f"market_increasing_{crop}", crop, "market",
             _phrasing("market", crop, i),
             _perturb_market_increasing, "Prepare for Harvest and Selling",
             [], ["market", "price increasing", "sell", "harvest"],
             "market.assessment.trend",
             ["MarketAgent"])

        # ---- Continue Monitoring (negative control) ----
        make(f"baseline_normal_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i),
             lambda f: f, "Continue Monitoring",
             [], ["favorable", "optimal", "suitable"],
             "none (negative control -- all fields left at the neutral baseline)",
             ["WeatherAgent", "SoilAgent", "SatelliteAgent", "MarketAgent", "HistoricalAgent"])

        ##############################################################
        # Known-limitation probe. A soil-pH excursion is a genuine
        # agronomic problem that warrants inspection, but
        # executive_engine.infer_decision() has no pH branch, so the
        # system can only answer "Continue Monitoring". Ground truth
        # is set to the agronomically correct action, and the scenario
        # is flagged so the report can attribute the resulting failure
        # to a capability gap rather than to noise.
        ##############################################################

        make(f"soil_ph_low_{crop}", crop, "yield",
             _phrasing("yield", crop, i),
             lambda f, p: _perturb_soil_ph(f, p, "low"), "Field Inspection",
             ["ph", "acidic", "soil ph", "outside the optimal range"], [],
             "soil.ph (below optimal)",
             ["SoilAgent"],
             probes_known_limitation=True)

        ##############################################################
        # Compound (two-signal) scenarios. Query type is "suitability"
        # when a market perturbation is involved (the only query type
        # whose expected-agent set includes MarketAgent alongside the
        # agronomic agents), "yield" otherwise.
        ##############################################################

        make(f"compound_water_market_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i + 2),
             _perturb_compound_water_market, "Immediate Irrigation",
             ["water stress", "drought", "irrigation", "rainfall"],
             ["market", "price increasing"],
             "satellite.water.ndwi + market.assessment.trend",
             ["SatelliteAgent", "WeatherAgent", "MarketAgent"])

        make(f"compound_nitrogen_market_{crop}", crop, "suitability",
             _phrasing("suitability", crop, (i + 1) % len(QUERY_PHRASINGS["suitability"])),
             _perturb_compound_nitrogen_market, "Apply Nitrogen Fertilizer",
             ["nitrogen", "fertilizer", "nutrient deficiency"],
             ["market", "price increasing"],
             "soil.nitrogen + market.assessment.trend",
             ["SoilAgent", "MarketAgent"])

        make(f"compound_organic_market_{crop}", crop, "suitability",
             _phrasing("suitability", crop, i),
             _perturb_compound_organic_market, "Apply Organic Manure",
             ["organic carbon", "organic matter", "manure", "compost"],
             ["market", "price increasing"],
             "soil.organic_carbon + market.assessment.trend",
             ["SoilAgent", "MarketAgent"])

        make(f"compound_vegetation_nitrogen_{crop}", crop, "yield",
             _phrasing("yield", crop, i),
             _perturb_compound_vegetation_nitrogen, "Field Inspection",
             ["vegetation", "crop health", "ndvi", "critical", "nitrogen", "nutrient deficiency"], [],
             "satellite.vegetation.ndvi + soil.nitrogen",
             ["SatelliteAgent", "SoilAgent"])

        make(f"compound_nitrogen_organic_{crop}", crop, "yield",
             _phrasing("yield", crop, i + 1),
             _perturb_compound_nitrogen_organic, "Apply Nitrogen Fertilizer",
             ["nitrogen", "fertilizer", "nutrient deficiency", "organic carbon", "organic matter"], [],
             "soil.nitrogen + soil.organic_carbon",
             ["SoilAgent"])

    return scenarios


REFERENCE_RECOMMENDATIONS = {
    "Immediate Irrigation": (
        "Irrigate the field immediately to relieve water stress; recheck soil moisture "
        "and satellite water-stress indices within 3-5 days before resuming a normal schedule."
    ),
    "Field Inspection": (
        "Walk the field to inspect for disease, pest damage, or nutrient deficiency; "
        "take tissue/soil samples from the worst-affected area before choosing a remedy."
    ),
    "Apply Nitrogen Fertilizer": (
        "Apply a nitrogen-based fertilizer at the crop's recommended rate for its current "
        "growth stage; retest soil nitrogen in 2-3 weeks to confirm correction."
    ),
    "Apply Organic Manure": (
        "Incorporate well-decomposed organic manure or compost to raise soil organic carbon; "
        "retest organic carbon levels after the next season."
    ),
    "Prepare for Harvest and Selling": (
        "With prices trending upward, prepare the harvest and target the best-ranked nearby "
        "market rather than the nearest one if the price differential outweighs transport cost."
    ),
    "Continue Monitoring": (
        "No significant risks are present; continue routine monitoring of weather, soil, and "
        "crop health without a specific corrective action this cycle."
    ),
}


def main():
    scenarios = build_scenarios()
    out_path = os.path.join(DATASET_DIR, "benchmark_queries.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "methodology": (
                "Ground truth is rule-derived from single-field perturbations of real "
                "AgriMind-collected context, checked against each crop profile's own "
                "numeric thresholds. NOT human-expert-verified. See module docstring "
                "in build_dataset.py for the full derivation."
            ),
            "n_scenarios": len(scenarios),
            "valid_decision_vocabulary": VALID_DECISIONS,
            "expected_agents_by_query_type": EXPECTED_AGENTS_BY_QUERY_TYPE,
            "scenarios": scenarios,
        }, f, indent=2, default=str)
    print(f"Wrote {len(scenarios)} scenarios to {out_path}")


if __name__ == "__main__":
    main()
