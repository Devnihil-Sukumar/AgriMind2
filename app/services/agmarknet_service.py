"""
==========================================================================
AgriMind

Agmarknet Service (data.gov.in) -- LIVE mandi prices

Fetches real daily mandi prices from the Government of India open-data
platform, replacing the synthetic data/market_prices.csv. Requires a
free data.gov.in API key in DATA_GOV_IN_API_KEY.

What the upstream API does and does not give us
-----------------------------------------------
The Agmarknet resource returns state, district, market, commodity,
arrival_date and min/max/modal price. It does NOT return:

  * **coordinates** -- it is a tabular price feed with no geometry, so
    market latitude/longitude is joined from the local reference table.
    That is geography, not price data, so joining it locally does not
    make the prices any less real.

  * **a trend** -- AgriMind's ranker needs Increasing/Decreasing/Stable,
    which is a statement about change over time and cannot be derived
    from a single day's snapshot. This service therefore persists each
    observed modal price and derives the trend by comparing against the
    previous observation for that market+commodity. The first time a
    market is ever seen the honest answer is "Unknown", not a guess.

Note on AGMARKNET_URL in .env: https://agmarknet.gov.in is the public
website, not an API, which is why the earlier scraping approach was a
dead end. The programmatic route is api.data.gov.in, configured
separately below.

Author : AgriMind Team
==========================================================================
"""

import json
import logging
import os
import threading
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


##########################################################################
# Configuration
##########################################################################

API_KEY = os.getenv("DATA_GOV_IN_API_KEY", "").strip()

# "Current Daily Price of Various Commodities from Various Markets (Mandi)"
RESOURCE_ID = os.getenv(
    "AGMARKNET_RESOURCE_ID",
    "9ef84268-d588-465a-a308-a864a43d0070"
)

API_BASE = os.getenv(
    "DATA_GOV_IN_URL",
    "https://api.data.gov.in/resource"
).rstrip("/")

REQUEST_TIMEOUT = float(os.getenv("AGMARKNET_TIMEOUT", "45"))

RETRIES = int(os.getenv("AGMARKNET_RETRIES", "2"))

MAX_RECORDS = int(os.getenv("AGMARKNET_LIMIT", "500"))

DEFAULT_STATE = os.getenv("AGMARKNET_STATE", "Tamil Nadu")

PRICE_HISTORY_PATH = os.getenv(
    "AGMARKNET_HISTORY",
    os.path.join("data", "market_price_history.json")
)

# Percent change below which a market counts as Stable rather than
# Increasing/Decreasing -- day-to-day mandi noise is routinely a few
# percent and should not be reported as a trend.
TREND_THRESHOLD_PCT = float(os.getenv("AGMARKNET_TREND_THRESHOLD", "2.0"))

##########################################################################
# Circuit breaker
#
# api.data.gov.in has extended outages (it was returning 502s, then
# timing out entirely, while this integration was written). Without a
# breaker, every pipeline run pays RETRIES x TIMEOUT -- roughly 135s --
# before falling back to a dataset that was always going to be used
# anyway. After this many consecutive failures the service stops trying
# until the cooldown expires, so a dead upstream costs one slow request
# rather than slowing down every request.
##########################################################################

FAILURE_THRESHOLD = int(os.getenv("AGMARKNET_FAILURE_THRESHOLD", "2"))

COOLDOWN_SECONDS = float(os.getenv("AGMARKNET_COOLDOWN", "900"))


##########################################################################
# Service
##########################################################################

class AgmarknetService:

    def __init__(self):

        self._lock = threading.Lock()
        self._history = self._load_history()
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    ####################################################################
    # Availability
    ####################################################################

    @property
    def configured(self):
        return bool(API_KEY)

    @property
    def circuit_open(self):
        """True while the breaker is holding calls off after repeated
        upstream failures."""
        return time.time() < self._circuit_open_until

    def _record_failure(self):

        self._consecutive_failures += 1

        if self._consecutive_failures >= FAILURE_THRESHOLD:

            self._circuit_open_until = time.time() + COOLDOWN_SECONDS

            logger.warning(
                "Agmarknet unreachable %d times in a row; pausing live "
                "market lookups for %.0f minutes and using the local "
                "dataset.",
                self._consecutive_failures,
                COOLDOWN_SECONDS / 60.0
            )

    def _record_success(self):

        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    ####################################################################
    # Price History (for trend derivation)
    ####################################################################

    def _load_history(self):

        try:
            with open(PRICE_HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_history(self):

        try:
            os.makedirs(
                os.path.dirname(PRICE_HISTORY_PATH) or ".",
                exist_ok=True
            )
            with open(PRICE_HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2)
        except OSError as error:
            logger.warning("Could not persist price history: %s", error)

    def derive_trend(self, market, commodity, modal_price):
        """Increasing/Decreasing/Stable relative to the last observation
        for this market+commodity, or Unknown the first time we see it.

        Deliberately NOT guessed: a single snapshot carries no trend
        information, and reporting one anyway would put an invented
        signal in front of a farmer's sell/hold decision.
        """

        key = f"{str(market).strip().lower()}|{str(commodity).strip().lower()}"

        previous = self._history.get(key, {}).get("modal_price")

        self._history[key] = {
            "modal_price": modal_price,
            "observed_at": datetime.now().isoformat(timespec="seconds"),
        }

        if previous in (None, 0):
            return "Unknown"

        change_pct = 100.0 * (modal_price - previous) / previous

        if change_pct > TREND_THRESHOLD_PCT:
            return "Increasing"

        if change_pct < -TREND_THRESHOLD_PCT:
            return "Decreasing"

        return "Stable"

    ####################################################################
    # Fetch
    ####################################################################

    def fetch_prices(self, crop, state=None):
        """Live mandi records for a crop, or None when the key is
        missing, the API is unreachable, or nothing matches."""

        if not self.configured:
            logger.info(
                "DATA_GOV_IN_API_KEY not set; market stays on the local "
                "dataset."
            )
            return None

        if self.circuit_open:
            logger.debug(
                "Agmarknet circuit breaker open; skipping live lookup."
            )
            return None

        state = state or DEFAULT_STATE

        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": MAX_RECORDS,
            "filters[state.keyword]": state,
            "filters[commodity]": str(crop).strip().title(),
        }

        url = f"{API_BASE}/{RESOURCE_ID}"

        for attempt in range(1, RETRIES + 2):

            try:

                response = requests.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )

                response.raise_for_status()

                records = response.json().get("records", [])

                ##################################################
                # A reachable API that simply has no rows for this
                # crop is a healthy response, not a failure -- it
                # must not trip the breaker.
                ##################################################

                self._record_success()

                if not records:
                    logger.info(
                        "Agmarknet returned no rows for %s in %s.",
                        crop,
                        state
                    )
                    return None

                return self._normalise(records, crop)

            except (requests.RequestException, ValueError) as error:

                logger.warning(
                    "Agmarknet attempt %d/%d failed: %s",
                    attempt,
                    RETRIES + 1,
                    error
                )

                if attempt > RETRIES:
                    self._record_failure()
                    return None

        return None

    ####################################################################
    # Normalise
    ####################################################################

    def _normalise(self, records, crop):
        """Map Agmarknet rows onto the column names market_tool already
        expects, so the ranker and assessor need no changes."""

        rows = []

        with self._lock:

            for record in records:

                try:
                    modal = float(record.get("modal_price") or 0)
                    minimum = float(record.get("min_price") or 0)
                    maximum = float(record.get("max_price") or 0)
                except (TypeError, ValueError):
                    continue

                if modal <= 0:
                    continue

                market = str(record.get("market", "")).strip()

                rows.append({
                    "State": str(record.get("state", "")).strip(),
                    "District": str(record.get("district", "")).strip(),
                    "Crop": str(crop).strip().title(),
                    "Market": market,
                    "Min_Price": minimum,
                    "Max_Price": maximum,
                    "Modal_Price": modal,
                    "Trend": self.derive_trend(market, crop, modal),
                    "Last_Updated": str(
                        record.get("arrival_date", "")
                    ).strip(),
                    "live_source": True,
                })

            self._save_history()

        return rows or None


##########################################################################
# Singleton
##########################################################################

agmarknet_service = AgmarknetService()
