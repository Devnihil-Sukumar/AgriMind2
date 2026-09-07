"""
==========================================================================
AgriMind

Multi-Source Data Collector

Collects all agricultural data sources using the dynamic crop profile.

Current Data Architecture
-------------------------
Weather       -> Open-Meteo
Soil          -> Local synthetic dataset
Market        -> Local synthetic dataset
Satellite     -> Sentinel-2 / Google Earth Engine
Historical    -> Historical memory

Author : AgriMind Team
==========================================================================
"""

import logging
from datetime import datetime

from app.config import ai_settings

logger = logging.getLogger(__name__)

from app.collectors.weather_collector import weather_collector
from app.collectors.soil_collector import soil_collector
from app.collectors.market_collector import market_collector
from app.collectors.satellite_collector import satellite_collector
from app.collectors.historical_collector import historical_collector


class DataCollector:

    ####################################################################
    # Collect
    ####################################################################

    def collect(

        self,

        crop_profile,

        latitude=None,

        longitude=None

    ):

        crop = crop_profile["crop"]

        ############################################################
        # Default Location
        ############################################################

        if latitude is None:

            latitude = ai_settings.DEFAULT_LATITUDE

        if longitude is None:

            longitude = ai_settings.DEFAULT_LONGITUDE

        latitude = float(

            latitude

        )

        longitude = float(

            longitude

        )

        ############################################################

        print("=" * 70)

        print(

            "MULTI-SOURCE DATA COLLECTION STARTED"

        )

        print("=" * 70)

        print(

            f"Crop      : {crop}"

        )

        print(

            f"Latitude  : {latitude}"

        )

        print(

            f"Longitude : {longitude}"

        )

        print()

        ################################################################
        # WEATHER
        ################################################################

        try:

            weather = weather_collector.collect(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

            print(

                "✓ Weather collected"

            )

        except Exception as e:

            logger.exception(

                "Weather collector raised unexpectedly"

            )

            print(

                f"✗ Weather collection failed: {e}"

            )

            weather = {

                "source": "weather",

                "status": "failed",

                "timestamp": None,

                "raw_data": {},

                "assessment": {

                    "status": "Unknown",

                    "temperature_status": "Unknown",

                    "rainfall_status": "Unknown",

                    "humidity_status": "Unknown",

                    "notes": f"Weather data unavailable: {e}"

                },

                "confidence": 0,

                "error": str(e)

            }

        ################################################################
        # SOIL
        ################################################################

        try:

            soil = soil_collector.collect(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

            print(

                "✓ Soil collected"

            )

        except Exception as e:

            logger.exception(

                "Soil collector raised unexpectedly"

            )

            print(

                f"✗ Soil collection failed: {e}"

            )

            soil = {

                "source": "soil",

                "status": "failed",

                "soil": None,

                "raw_data": None,

                "assessment": {

                    "soil_health_score": 0,

                    "notes": f"Soil data unavailable: {e}"

                },

                "confidence": 0,

                "error": str(e)

            }

        ############################################################
        # Normalize Soil Location
        ############################################################

        soil_data = soil.get(

            "soil",

            soil.get(

                "raw_data",

                {}

            )

        ) or {}

        soil_district = soil_data.get(

            "district"

        )

        soil_state = soil_data.get(

            "state"

        )

        ################################################################
        # MARKET
        ################################################################

        try:

            market = market_collector.collect(

                crop_profile=crop_profile,

                district=soil_district,

                latitude=latitude,

                longitude=longitude

            )

            print(

                "✓ Market collected"

            )

        except Exception as e:

            logger.exception(

                "Market collector raised unexpectedly"

            )

            print(

                f"✗ Market collection failed: {e}"

            )

            market = {

                "source": "market",

                "status": "failed",

                "market": None,

                "nearest_market": None,

                "top_markets": [],

                "raw_data": None,

                "assessment": {

                    "trend": "Unknown",

                    "notes": f"Market data unavailable: {e}"

                },

                "confidence": 0,

                "error": str(e)

            }

        ################################################################
        # SATELLITE
        ################################################################

        print(

            "Collecting Sentinel-2 imagery..."

        )

        try:

            satellite = satellite_collector.collect(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

        except Exception as e:

            logger.exception(

                "Satellite collector raised unexpectedly"

            )

            print(

                f"✗ Satellite collection failed: {e}"

            )

            satellite = {

                "source": "satellite",

                "status": "failed",

                "confidence": 0,

                "error": str(e),

                "timestamp": datetime.utcnow().isoformat(),

                "location": {

                    "latitude": latitude,

                    "longitude": longitude

                }

            }

        ############################################################
        # Satellite success
        ############################################################

        if satellite.get(

            "status"

        ) == "success":

            vegetation = satellite.get(

                "vegetation",

                {}

            )

            water = satellite.get(

                "water",

                {}

            )

            soil_satellite = satellite.get(

                "soil",

                {}

            )

            imagery = satellite.get(

                "imagery",

                {}

            )

            ndvi = vegetation.get(

                "ndvi",

                0

            )

            evi = vegetation.get(

                "evi",

                0

            )

            savi = vegetation.get(

                "savi",

                0

            )

            health = vegetation.get(

                "health",

                "Unknown"

            )

            ndwi = water.get(

                "ndwi",

                0

            )

            water_stress = water.get(

                "stress",

                "Unknown"

            )

            soil_exposure = soil_satellite.get(

                "exposure",

                "Unknown"

            )

            cloud_cover = imagery.get(

                "cloud_cover",

                0

            )

            print(

                f"✓ Satellite collected "

                f"(NDVI={float(ndvi):.3f}, "

                f"Cloud={cloud_cover}%)"

            )

            satellite_summary = f"""
NDVI : {ndvi}
EVI : {evi}
SAVI : {savi}
Vegetation Health : {health}
NDWI : {ndwi}
Water Stress : {water_stress}
Soil Exposure : {soil_exposure}
Cloud Cover : {cloud_cover}%
"""

        ################################################################
        # Satellite failure
        ################################################################

        else:

            print(

                "⚠ Satellite skipped"

            )

            satellite_error = satellite.get(

                "error",

                "Satellite data unavailable."

            )

            print(

                f"Reason : {satellite_error}"

            )

            satellite_summary = f"""
Satellite data unavailable.

Reason:
{satellite_error}
"""

        ################################################################
        # WEATHER SUMMARY
        ################################################################

        weather_raw = weather.get(

            "raw_data",

            {}

        ) or {}

        weather_summary = f"""
Temperature : {weather_raw.get('temperature', 'Unknown')}
Humidity : {weather_raw.get('humidity', 'Unknown')}
Rainfall : {weather_raw.get('rainfall', 'Unknown')}
Wind Speed : {weather_raw.get('wind_speed', 'Unknown')}
Pressure : {weather_raw.get('pressure', 'Unknown')}
"""

        ################################################################
        # SOIL SUMMARY
        ################################################################

        soil_raw = soil.get(

            "raw_data",

            soil_data

        ) or {}

        soil_summary = f"""
State : {soil_raw.get('state', soil_state or 'Unknown')}
District : {soil_raw.get('district', soil_district or 'Unknown')}
pH : {soil_raw.get('ph', 'Unknown')}
Nitrogen : {soil_raw.get('nitrogen', 'Unknown')}
Organic Carbon : {soil_raw.get('organic_carbon', 'Unknown')}
Sand : {soil_raw.get('sand_percent', 'Unknown')}
Clay : {soil_raw.get('clay_percent', 'Unknown')}
Silt : {soil_raw.get('silt_percent', 'Unknown')}
CEC : {soil_raw.get('cec', 'Unknown')}
Distance : {soil_raw.get('distance_km', 'Unknown')} km
"""

        ################################################################
        # MARKET SUMMARY
        ################################################################

        nearest_market = market.get(

            "nearest_market"

        )

        top_markets = market.get(

            "top_markets",

            []

        )

        market_raw = market.get(

            "raw_data",

            {}

        ) or {}

        if nearest_market:

            nearest_name = nearest_market.get(

                "market",

                "Unknown"

            )

            nearest_distance = nearest_market.get(

                "distance_km",

                "Unknown"

            )

            nearest_price = nearest_market.get(

                "price",

                "Unknown"

            )

            nearest_trend = nearest_market.get(

                "trend",

                "Unknown"

            )

        else:

            nearest_name = "Unavailable"

            nearest_distance = "Unknown"

            nearest_price = "Unknown"

            nearest_trend = "Unknown"

        ############################################################
        # Best ranked market
        ############################################################

        if top_markets:

            best_market = top_markets[0]

            best_market_name = best_market.get(

                "market",

                "Unknown"

            )

            best_market_price = best_market.get(

                "price",

                "Unknown"

            )

            best_market_distance = best_market.get(

                "distance_km",

                "Unknown"

            )

            best_market_trend = best_market.get(

                "trend",

                "Unknown"

            )

        else:

            best_market_name = "Unavailable"

            best_market_price = "Unknown"

            best_market_distance = "Unknown"

            best_market_trend = "Unknown"

        market_summary = f"""
Nearest Market : {nearest_name}
Nearest Distance : {nearest_distance} km
Nearest Market Price : {nearest_price}
Nearest Market Trend : {nearest_trend}

Best Ranked Market : {best_market_name}
Best Market Price : {best_market_price}
Best Market Distance : {best_market_distance} km
Best Market Trend : {best_market_trend}

Markets Evaluated : {len(top_markets)}
Crop : {market_raw.get('Crop', crop)}
"""

        ################################################################
        # HISTORICAL
        ################################################################

        historical = historical_collector.collect(

            crop_profile=crop_profile,

            weather=weather_summary,

            soil=soil_summary,

            satellite=satellite_summary,

            market=market_summary

        )

        print(

            "✓ Historical data collected"

        )

        ################################################################
        # FINAL OUTPUT
        ################################################################

        print()

        print("=" * 70)

        print(

            "ALL SOURCES COLLECTED"

        )

        print("=" * 70)

        return {

            "metadata": {

                "collection_time":

                    datetime.utcnow().isoformat(),

                "crop":

                    crop,

                "crop_profile":

                    crop_profile,

                "location": {

                    "latitude":

                        latitude,

                    "longitude":

                        longitude,

                    "district":

                        soil_district,

                    "state":

                        soil_state

                }

            },

            "weather":

                weather,

            "soil":

                soil,

            "market":

                market,

            "satellite":

                satellite,

            "historical":

                historical

        }


##########################################################################
# Singleton
##########################################################################

data_collector = DataCollector()