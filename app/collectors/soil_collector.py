"""
==========================================================================
AgriMind

Soil Collector

Responsibilities
----------------
1. Call SoilTool.
2. Normalize soil response.
3. Return standardized soil data.

Author : AgriMind Team
==========================================================================
"""

import logging

from app.tools.soil_tool import soil_tool

logger = logging.getLogger(__name__)


class SoilCollector:

    ####################################################################
    # Collect
    ####################################################################

    def collect(

        self,

        crop_profile,

        latitude,

        longitude

    ):

        try:

            result = soil_tool.execute(

                crop_profile=crop_profile,

                latitude=latitude,

                longitude=longitude

            )

        except Exception as e:

            logger.warning(

                "Soil collection failed: %s",
                e

            )

            result = {

                "status": "failed",

                "assessment": {

                    "soil_health_score": 0,

                    "ph_status": "Unknown",

                    "notes":
                        "Soil data unavailable: "
                        + str(e)

                },

                "error": str(e)

            }

        if result.get(

            "status"

        ) != "success":

            assessment = result.get(

                "assessment",

                {}

            ) or {}

            ############################################################
            # context_agent.py and executive/summary_generator.py index
            # soil["assessment"]["soil_health_score"] directly, so this
            # key must survive every failure path, not just the tool's
            # own status!=success branch.
            ############################################################

            if "soil_health_score" not in assessment:

                assessment["soil_health_score"] = 0

            return {

                "source": "soil",

                "status": "failed",

                "soil": None,

                "raw_data": None,

                "assessment": assessment,

                "confidence": 0

            }

        return {

            "source": "soil",

            "status": "success",

            "soil":

                result.get(

                    "data",

                    result.get(

                        "soil"

                    )

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

soil_collector = SoilCollector()