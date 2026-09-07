"""
==========================================================================
AgriMind

SoilGrids Service (ISRIC) -- LIVE soil data

Replaces the synthetic data/soil_data.csv lookup with real, measured
soil properties from ISRIC's SoilGrids 250m global product. No API key
is required (SOILGRIDS_URL is already in .env).

Why this exists
---------------
Soil was one of two data sources the evaluation had to declare as
synthetic. SoilGrids maps 1:1 onto AgriMind's soil schema, so the
pipeline can report genuinely measured soil rather than a nearest-point
lookup in a generated CSV.

Two real-world properties of this API shape the design:

1. **Coverage gaps.** SoilGrids masks built-up land and some pixels
   simply have no value -- Coimbatore city centre returns nulls while
   farmland 20km south returns pH 7.4. A null is a legitimate answer,
   not an error, so this service returns None and lets the caller fall
   back rather than inventing a number.

2. **Rate limiting.** ISRIC allows roughly 5 requests/minute and is
   slow (multi-second responses). The evaluation harness issues far
   more than that, so responses are cached on disk keyed by rounded
   coordinates. At 250m native resolution, rounding to 3 decimals
   (~110m) is finer than the underlying raster, so caching costs no
   real precision.

Unit conversions follow the SoilGrids v2.0 contract, where every value
is an integer and `raw / d_factor` yields the layer's target_units.
Verified against a live response at (10.85, 77.05), where the raw
sand/clay/silt triple summed to exactly 1000 -- the check that pins the
texture divisor at 10 rather than 100:

    property  raw  d_factor  target_units  -> AgriMind field
    phh2o      74        10  pH             7.4   ph
    sand      482        10  %             48.2   sand_percent
    clay      267        10  %             26.7   clay_percent
    silt      251        10  %             25.1   silt_percent
    cec       235        10  cmol(c)/kg    23.5   cec
    bdod      144       100  kg/dm3         1.44  bulk_density
    nitrogen  241       100  g/kg           2.41  -> /10 = 0.241 %
    soc       266        10  g/kg          26.6   -> /10 = 2.66  %

Nitrogen and organic carbon are additionally divided by 10 because
AgriMind's classifiers work in percent while SoilGrids targets g/kg.

Field capacity and wilting point are not SoilGrids properties; they are
derived from texture and organic matter using the Saxton & Rawls (2006)
pedotransfer functions, and flagged as derived rather than measured.

Author : AgriMind Team
==========================================================================
"""

import json
import logging
import os
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


##########################################################################
# Configuration
##########################################################################

SOILGRIDS_URL = os.getenv(
    "SOILGRIDS_URL",
    "https://rest.isric.org"
).rstrip("/")

REQUEST_TIMEOUT = float(os.getenv("SOILGRIDS_TIMEOUT", "60"))

RETRIES = int(os.getenv("SOILGRIDS_RETRIES", "2"))

# ISRIC allows ~5 requests/minute; stay under it.
MIN_SECONDS_BETWEEN_CALLS = float(os.getenv("SOILGRIDS_MIN_INTERVAL", "13"))

CACHE_PATH = os.getenv(
    "SOILGRIDS_CACHE",
    os.path.join("data", "soilgrids_cache.json")
)

# 0-5cm and 5-15cm are the agronomically relevant root-zone layers.
DEPTH = os.getenv("SOILGRIDS_DEPTH", "0-5cm")

PROPERTIES = [
    "phh2o",
    "nitrogen",
    "soc",
    "sand",
    "clay",
    "silt",
    "cec",
    "bdod",
]

# raw integer -> the value AgriMind stores (see module docstring table).
# For most properties this is SoilGrids' own d_factor; nitrogen and soc
# carry an extra x10 because AgriMind works in percent, not g/kg.
CONVERSIONS = {
    "phh2o": 10.0,      # d_factor 10  -> pH
    "nitrogen": 1000.0,  # d_factor 100 -> g/kg, then /10 -> %
    "soc": 100.0,        # d_factor 10  -> g/kg, then /10 -> %
    "sand": 10.0,        # d_factor 10  -> %
    "clay": 10.0,        # d_factor 10  -> %
    "silt": 10.0,        # d_factor 10  -> %
    "cec": 10.0,         # d_factor 10  -> cmol(c)/kg
    "bdod": 100.0,       # d_factor 100 -> kg/dm3 (== g/cm3)
}


##########################################################################
# Service
##########################################################################

class SoilGridsService:

    def __init__(self):

        self._lock = threading.Lock()
        self._last_call_at = 0.0
        self._cache = self._load_cache()

    ####################################################################
    # Cache
    ####################################################################

    def _load_cache(self):

        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self):

        try:
            os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except OSError as error:
            logger.warning("Could not persist SoilGrids cache: %s", error)

    @staticmethod
    def _cache_key(latitude, longitude):
        # 3 decimals ~= 110m, finer than SoilGrids' own 250m raster.
        return f"{round(float(latitude), 3)},{round(float(longitude), 3)}"

    ####################################################################
    # Pacing
    ####################################################################

    def _wait_for_slot(self):
        """ISRIC rate-limits aggressively; space calls out rather than
        being throttled mid-evaluation."""

        elapsed = time.time() - self._last_call_at

        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)

        self._last_call_at = time.time()

    ####################################################################
    # Fetch
    ####################################################################

    def fetch(self, latitude, longitude):
        """Return measured soil properties, or None when SoilGrids has
        no data for this location (a real and expected outcome over
        built-up land) or is unreachable."""

        key = self._cache_key(latitude, longitude)

        with self._lock:

            if key in self._cache:
                return self._cache[key]

            result = self._fetch_uncached(latitude, longitude)

            ##########################################################
            # Cache negatives too: a null pixel stays null, and
            # re-asking costs a rate-limited round trip for nothing.
            ##########################################################

            self._cache[key] = result
            self._save_cache()

            return result

    def _fetch_uncached(self, latitude, longitude):

        url = f"{SOILGRIDS_URL}/soilgrids/v2.0/properties/query"

        params = [
            ("lat", float(latitude)),
            ("lon", float(longitude)),
            ("depth", DEPTH),
            ("value", "mean"),
        ] + [("property", p) for p in PROPERTIES]

        for attempt in range(1, RETRIES + 2):

            try:

                self._wait_for_slot()

                response = requests.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )

                response.raise_for_status()

                return self._parse(response.json(), latitude, longitude)

            except requests.RequestException as error:

                logger.warning(
                    "SoilGrids attempt %d/%d failed: %s",
                    attempt,
                    RETRIES + 1,
                    error
                )

                if attempt > RETRIES:
                    return None

                time.sleep(2 * attempt)

        return None

    ####################################################################
    # Parse
    ####################################################################

    def _parse(self, payload, latitude, longitude):

        layers = (
            payload
            .get("properties", {})
            .get("layers", [])
        )

        values = {}

        for layer in layers:

            name = layer.get("name")

            depths = layer.get("depths") or []

            if not depths:
                continue

            raw = (depths[0].get("values") or {}).get("mean")

            if raw is None:
                continue

            divisor = CONVERSIONS.get(name)

            values[name] = (
                float(raw) / divisor if divisor else float(raw)
            )

        ##############################################################
        # pH and texture are the minimum needed for a soil assessment
        # worth reporting. Without them this location is a coverage
        # gap, which the caller handles by falling back.
        ##############################################################

        if "phh2o" not in values or "clay" not in values:
            logger.info(
                "SoilGrids has no usable data at (%s, %s) -- coverage gap.",
                latitude,
                longitude
            )
            return None

        sand = values.get("sand", 0.0)
        clay = values.get("clay", 0.0)
        soc = values.get("soc", 0.0)

        field_capacity, wilting_point = self.estimate_water_retention(
            sand,
            clay,
            soc
        )

        return {
            "ph": round(values["phh2o"], 2),
            "nitrogen_percent": round(values.get("nitrogen", 0.0), 4),
            "organic_carbon_percent": round(soc, 3),
            "sand_percent": round(sand, 1),
            "clay_percent": round(clay, 1),
            "silt_percent": round(values.get("silt", 0.0), 1),
            "cec": round(values.get("cec", 0.0), 2),
            "bulk_density": round(values.get("bdod", 0.0), 3),
            "field_capacity": field_capacity,
            "wilting_point": wilting_point,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "depth": DEPTH,
            "source": "ISRIC SoilGrids v2.0",
            "live_source": True,
        }

    ####################################################################
    # Water Retention (derived, not measured)
    ####################################################################

    @staticmethod
    def estimate_water_retention(sand_percent, clay_percent, soc_percent):
        """Saxton & Rawls (2006) pedotransfer functions.

        SoilGrids does not publish field capacity or wilting point, so
        these are DERIVED from texture and organic matter rather than
        measured, and are labelled as such in the tool's metadata.
        Organic matter is taken as organic carbon x 1.724 (van Bemmelen).
        """

        S = max(0.0, min(1.0, sand_percent / 100.0))
        C = max(0.0, min(1.0, clay_percent / 100.0))
        OM = max(0.0, soc_percent * 1.724)

        # Wilting point (theta at 1500 kPa)
        theta_1500 = (
            -0.024 * S
            + 0.487 * C
            + 0.006 * OM
            + 0.005 * (S * OM)
            - 0.013 * (C * OM)
            + 0.068 * (S * C)
            + 0.031
        )
        wilting_point = theta_1500 + (0.14 * theta_1500 - 0.02)

        # Field capacity (theta at 33 kPa)
        theta_33 = (
            -0.251 * S
            + 0.195 * C
            + 0.011 * OM
            + 0.006 * (S * OM)
            - 0.027 * (C * OM)
            + 0.452 * (S * C)
            + 0.299
        )
        field_capacity = theta_33 + (
            1.283 * theta_33 ** 2
            - 0.374 * theta_33
            - 0.015
        )

        return (
            round(max(0.0, min(1.0, field_capacity)), 3),
            round(max(0.0, min(1.0, wilting_point)), 3),
        )


##########################################################################
# Singleton
##########################################################################

soilgrids_service = SoilGridsService()
