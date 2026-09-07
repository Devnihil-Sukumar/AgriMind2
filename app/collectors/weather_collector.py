"""
==========================================================================
AgriMind

Weather Collector

Collects weather information using the dynamic crop profile.

Author : AgriMind Team
==========================================================================
"""

import logging

from app.tools.weather_tool import weather_tool

logger = logging.getLogger(__name__)


class WeatherCollector:

    """
    Weather Collector

    Responsibilities
    ----------------
    1. Call WeatherTool.
    2. Normalize the response.
    3. Return standardized weather data.
    """

    ####################################################################
    # Collect
    ####################################################################

    def collect(

        self,

        crop_profile,

        latitude=None,

        longitude=None

    ):

        ################################################################
        # Open-Meteo is a live network call. A timeout, DNS failure or
        # proxy block must degrade this ONE source rather than crash
        # the whole multi-agent pipeline before the planner even runs.
        ################################################################

        try:

            result = weather_tool.execute(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

        except Exception as e:

            logger.warning(

                "Weather collection failed: %s",
                e

            )

            return {

                "source": "weather",

                "status": "failed",

                "timestamp": None,

                "raw_data": {},

                "assessment": {

                    "status": "Unknown",

                    "temperature_status": "Unknown",

                    "rainfall_status": "Unknown",

                    "humidity_status": "Unknown",

                    "notes":
                        "Weather data unavailable: "
                        + str(e)

                },

                "confidence": 0,

                "error": str(e)

            }

        if result.get("status") != "success":

            return {

                "source": "weather",

                "status": "failed",

                "timestamp": None,

                "raw_data": result.get("data", {}),

                "assessment": {

                    "status": "Unknown",

                    "temperature_status": "Unknown",

                    "rainfall_status": "Unknown",

                    "humidity_status": "Unknown",

                    "notes": "Weather source returned no usable data."

                },

                "confidence": 0

            }

        return {

            "source": "weather",

            "status": result["status"],

            "timestamp": result["data"].get("time"),

            "raw_data": result["data"],

            "assessment": result["assessment"],

            "confidence": result["confidence"]

        }


##########################################################################

weather_collector = WeatherCollector()