"""
==========================================================================
AgriMind

Local Market Tool

Uses synthetic, scenario-controlled Tamil Nadu market data.

Responsibilities
----------------
1. Load local market dataset.
2. Filter crop.
3. Find nearby markets.
4. Rank top markets.
5. Assess market conditions.
6. Return standardized market data.

Author : AgriMind Team
==========================================================================
"""

import logging
import os

import pandas as pd

from app.algorithms.market_ranker import market_ranker
from app.services.agmarknet_service import agmarknet_service

logger = logging.getLogger(__name__)

CSV_PATH = "data/market_prices.csv"

##########################################################################
# Set MARKET_LIVE_SOURCE=0 to force the local dataset.
##########################################################################

USE_LIVE_MARKET = os.getenv(
    "MARKET_LIVE_SOURCE",
    "1"
).strip().lower() not in ("0", "false", "no")


class MarketTool:

    ####################################################################
    # Constructor
    ####################################################################

    def __init__(self):

        self._csv_mtime = None

        self._load()

    ####################################################################
    # Load / Reload
    #
    # market_tool is a module-level singleton created once at import
    # time, but data/market_prices.csv is meant to be refreshed daily
    # by scripts/update_market_prices.py while the app keeps running.
    # Re-reading only when the file's mtime has actually changed keeps
    # a long-lived process from ever seeing yesterday's prices without
    # paying pandas.read_csv on every single call.
    ####################################################################

    def _load(self):

        self.df = pd.read_csv(
            CSV_PATH
        )

        self.df.columns = (

            self.df.columns

            .str.strip()

        )

        self._csv_mtime = os.path.getmtime(CSV_PATH)

    def _reload_if_stale(self):

        try:

            mtime = os.path.getmtime(CSV_PATH)

        except OSError:

            return

        if mtime != self._csv_mtime:
            self._load()

    ####################################################################
    # Get Crop Markets
    ####################################################################

    def get_live_markets(

        self,

        crop

    ):
        """Live Agmarknet rows with coordinates joined from the local
        reference table. None on any failure, so the caller falls back.

        Agmarknet carries no geometry, and the ranker scores partly on
        distance, so a live row that cannot be geo-located is dropped
        rather than given invented coordinates -- a market whose
        position we do not know cannot be honestly ranked by distance.
        """

        rows = agmarknet_service.fetch_prices(crop)

        if not rows:
            return None

        ############################################################
        # Build a market-name -> coordinates index from the local
        # reference data (geography only; prices come from the API).
        ############################################################

        reference = {}

        for _, row in self.df.iterrows():
            name = str(row.get("Market", "")).strip().lower()
            if name:
                reference[name] = (
                    row.get("Latitude"),
                    row.get("Longitude")
                )

        located = []

        for row in rows:

            coords = reference.get(
                str(row.get("Market", "")).strip().lower()
            )

            if not coords or coords[0] is None:
                continue

            row["Latitude"] = float(coords[0])
            row["Longitude"] = float(coords[1])

            located.append(row)

        if not located:
            logger.info(
                "Agmarknet returned %d rows for %s but none matched a "
                "known market location; using local dataset.",
                len(rows),
                crop
            )
            return None

        return located

    def get_markets(

        self,

        crop

    ):

        crop = str(

            crop

        ).strip().title()

        result = self.df[

            self.df["Crop"].astype(

                str

            ).str.strip().str.title()

            == crop

        ]

        return [

            row.to_dict()

            for _, row in result.iterrows()

        ]

    ####################################################################
    # Assess Market
    ####################################################################

    def assess_market(

        self,

        markets,

        crop_profile

    ):

        if not markets:

            return {

                "market_score": 0,

                "trend": "Unknown",

                "recommendation":

                    "No market data available.",

                "opportunities": [],

                "risks": []

            }

        best = markets[0]

        trend = str(

            best.get(

                "Trend",

                "Stable"

            )

        ).title()

        score = 100

        opportunities = []

        risks = []

        if trend == "Increasing":

            opportunities.append(

                "Market prices are increasing."

            )

        elif trend == "Stable":

            score -= 5

        elif trend == "Decreasing":

            score -= 20

            risks.append(

                "Market prices are decreasing."

            )

        elif trend == "Volatile":

            score -= 10

            risks.append(

                "Market prices are volatile."

            )

        top_price = float(

            best.get(

                "Modal_Price",

                0

            )

        )

        recommendation = (

            f"Best ranked market is "

            f"{best.get('Market', 'Unknown')} "

            f"with modal price {top_price}."

        )

        if len(markets) > 1:

            opportunities.append(

                "Multiple nearby markets are available for comparison."

            )

        return {

            "market_score":

                max(

                    score,

                    0

                ),

            "trend":

                trend,

            "recommendation":

                recommendation,

            "opportunities":

                opportunities,

            "risks":

                risks

        }

    ####################################################################
    # Execute
    ####################################################################

    def execute(

        self,

        crop_profile,

        district=None,

        latitude=None,

        longitude=None

    ):

        self._reload_if_stale()

        crop = crop_profile["crop"]

        markets = None

        live_source = False

        if USE_LIVE_MARKET:

            try:

                markets = self.get_live_markets(

                    crop

                )

                live_source = bool(markets)

            except Exception as error:

                ##################################################
                # Never let a live-feed problem fail the market
                # stage; the local dataset sits underneath it.
                ##################################################

                logger.warning(
                    "Agmarknet lookup failed, falling back to local "
                    "dataset: %s",
                    error
                )

                markets = None

        if not markets:

            markets = self.get_markets(

                crop

            )

        if not markets:

            return {

                "agent":

                    "market_tool",

                "status":

                    "failed",

                "confidence":

                    0,

                "data":

                    {},

                "assessment": {

                    "market_score":

                        0,

                    "trend":

                        "Unknown",

                    "recommendation":

                        f"No market data available for {crop}.",

                    "opportunities": [],

                    "risks": []

                }

            }

        ############################################################
        # Determine Farm Coordinates
        ############################################################

        if latitude is None and district:

            match = self.df[

                self.df["District"]

                .astype(str)

                .str.strip()

                .str.lower()

                == str(district)

                .strip()

                .lower()

            ]

            if not match.empty:

                latitude = float(

                    match.iloc[0]["Latitude"]

                )

                longitude = float(

                    match.iloc[0]["Longitude"]

                )

        ############################################################
        # Fallback to first market
        ############################################################

        if latitude is None or longitude is None:

            latitude = float(

                markets[0]["Latitude"]

            )

            longitude = float(

                markets[0]["Longitude"]

            )
        ############################################################
        # Rank
        ############################################################

        ranked = market_ranker.rank(

            markets,

            latitude,

            longitude,

            top_k=5

        )

        if not ranked:

            return {

                "agent":

                    "market_tool",

                "status":

                    "failed",

                "confidence":

                    0,

                "data":

                    {},

                "assessment": {

                    "market_score":

                        0,

                    "trend":

                        "Unknown",

                    "recommendation":

                        "Unable to rank markets.",

                    "opportunities": [],

                    "risks": []

                }

            }

        ############################################################

        top_markets = []

        for item in ranked:

            top_markets.append(

                {

                    "market":

                        item.get(

                            "Market"

                        ),

                    "district":

                        item.get(

                            "District"

                        ),

                    "price":

                        float(

                            item.get(

                                "Modal_Price",

                                0

                            )

                        ),

                    "trend":

                        item.get(

                            "Trend",

                            "Unknown"

                        ),

                    "distance_km":

                        float(

                            item.get(

                                "distance_km",

                                0

                            )

                        ),

                    "market_score":

                        float(

                            item.get(

                                "market_score",

                                0

                            )

                        ),

                    "rank":

                        int(

                            item.get(

                                "rank",

                                0

                            )

                        )

                }

            )

        ############################################################

        assessment = self.assess_market(

            ranked,

            crop_profile

        )

        ############################################################

        return {

            "agent":

                "market_tool",

            "status":

                "success",

            "confidence":

                round(

                    assessment["market_score"]

                    / 100,

                    2

                ),

            "market":

                top_markets[0]["market"],

            "nearest_market":

                min(

                    top_markets,

                    key=lambda x:

                        x["distance_km"]

                ),

            "top_markets":

                top_markets,

            "data":

                {

                    "Crop":

                        crop,

                    "TopMarkets":

                        top_markets

                },

            "assessment":

                assessment,

            "metadata": {

                "source":

                    "Agmarknet / data.gov.in (live mandi prices)"
                    if live_source
                    else "Synthetic Local Dataset",

                "live_source":

                    live_source,

                ##########################################################
                # Coordinates are joined from the local reference table
                # even on the live path -- Agmarknet has no geometry.
                ##########################################################

                "coordinates_source":

                    "local reference table"
                    if live_source
                    else "local dataset",

                "market_count":

                    len(

                        markets

                    ),

                "top_market_count":

                    len(

                        top_markets

                    )

            }

        }


##########################################################################

market_tool = MarketTool()