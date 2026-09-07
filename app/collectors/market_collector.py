"""
==========================================================================
AgriMind

Market Collector

Responsibilities
----------------
1. Call MarketTool.
2. Normalize market response.
3. Preserve nearest market.
4. Preserve top-5 market rankings.
5. Return standardized market data.

Author : AgriMind Team
==========================================================================
"""

import logging

from app.tools.market_tool import market_tool

logger = logging.getLogger(__name__)


class MarketCollector:

    ####################################################################
    # Collect
    ####################################################################

    def collect(

        self,

        crop_profile,

        district=None,

        latitude=None,

        longitude=None

    ):

        try:

            result = market_tool.execute(

                crop_profile=crop_profile,

                district=district,

                latitude=latitude,

                longitude=longitude

            )

        except Exception as e:

            logger.warning(

                "Market collection failed: %s",
                e

            )

            result = {

                "status": "failed",

                "assessment": {

                    "trend": "Unknown",

                    "notes":
                        "Market data unavailable: "
                        + str(e)

                },

                "error": str(e)

            }

        if result.get(

            "status"

        ) != "success":

            return {

                "source": "market",

                "status": "failed",

                "market": None,

                "nearest_market": None,

                "top_markets": [],

                "raw_data": None,

                "assessment":

                    result.get(

                        "assessment",

                        {}

                    ),

                "confidence": 0

            }

        return {

            "source": "market",

            "status": "success",

            "market":

                result.get(

                    "market"

                ),

            "nearest_market":

                result.get(

                    "nearest_market"

                ),

            "top_markets":

                result.get(

                    "top_markets",

                    []

                ),

            "raw_data":

                result.get(

                    "data",

                    {}

                ),

            "assessment":

                result.get(

                    "assessment",

                    {}

                ),

            "confidence":

                result.get(

                    "confidence",

                    0

                ),

            "metadata":

                result.get(

                    "metadata",

                    {}

                )

        }


##########################################################################

market_collector = MarketCollector()