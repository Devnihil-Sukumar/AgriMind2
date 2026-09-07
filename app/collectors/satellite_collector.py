"""
==========================================================================
AgriMind

Satellite Collector

Collects Sentinel-2 satellite information using the dynamic crop profile.

Author : AgriMind Team
==========================================================================
"""

from datetime import datetime

from app.tools.satellite_tool import satellite_tool


class SatelliteCollector:

    """
    Satellite Collector

    Responsibilities
    ----------------
    1. Validate coordinates.
    2. Execute SatelliteTool.
    3. Normalize satellite response.
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

        ############################################################
        # Validate Coordinates
        ############################################################

        if latitude is None or longitude is None:

            return {

                "source": "satellite",

                "status": "failed",

                "confidence": 0,

                "error": "Latitude and Longitude are required.",

                "timestamp": datetime.utcnow().isoformat(),

                "location": {

                    "latitude": latitude,

                    "longitude": longitude

                }

            }

        ############################################################

        try:

            latitude = float(latitude)

            longitude = float(longitude)

        except (TypeError, ValueError):

            return {

                "source": "satellite",

                "status": "failed",

                "confidence": 0,

                "error": "Invalid coordinate format.",

                "timestamp": datetime.utcnow().isoformat(),

                "location": {

                    "latitude": latitude,

                    "longitude": longitude

                }

            }

        ############################################################
        # Execute Satellite Tool
        ############################################################

        try:

            result = satellite_tool.execute(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

        except Exception as e:

            return {

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
        # Normalize Success Response
        ############################################################

        data = result.get("data", {})

        assessment = result.get("assessment", {})

        return {

            "source": "satellite",

            "status": result.get("status", "failed"),

            "confidence": result.get("confidence", 0),

            ############################################################
            # satellite_tool.execute() sets "error" on its own failure
            # branch (e.g. an AttributeError from a missing setting, or
            # "No Sentinel-2 images found."). Without carrying it
            # through here, callers only ever see the generic
            # "Satellite data unavailable." fallback and the real
            # cause is lost.
            ############################################################

            "error": result.get("error"),

            "timestamp": datetime.utcnow().isoformat(),

            "location": {

                "latitude": latitude,

                "longitude": longitude

            },

            "imagery": {

                "acquisition_date":

                    data.get("acquisition_date"),

                "cloud_cover":

                    data.get("cloud_cover"),

                "valid_pixels":

                    data.get("valid_pixels")

            },

            "vegetation": {

                "ndvi":

                    data.get("ndvi"),

                "evi":

                    data.get("evi"),

                "savi":

                    data.get("savi"),

                "health":

                    assessment.get(

                        "crop_health",

                        "Unknown"

                    )

            },

            "water": {

                "ndwi":

                    data.get("ndwi"),

                "stress":

                    assessment.get(

                        "water_stress",

                        "Unknown"

                    )

            },

            "soil": {

                "exposure":

                    assessment.get(

                        "soil_exposure",

                        "Unknown"

                    )

            },

            "assessment": {

                "vegetation_score":

                    assessment.get(

                        "vegetation_score",

                        0

                    ),

                "recommendation":

                    assessment.get(

                        "recommendation",

                        "Unavailable"

                    )

            }

        }


##########################################################################

satellite_collector = SatelliteCollector()