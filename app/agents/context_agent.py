"""
==========================================================================
AgriMind

Context Understanding Agent

Author : AgriMind Team
==========================================================================
"""


class ContextAgent:

    """
    Builds the unified farm context.
    """

    def analyze(self, data):

        weather = data["weather"]
        soil = data["soil"]
        satellite = data["satellite"]
        market = data["market"]
        historical = data["historical"]

        crop_profile = data["metadata"]["crop_profile"]
        crop = crop_profile["crop"]

        ############################################################
        # Resolve farm location robustly
        #
        # Preferred source:
        #   soil["location"]
        #
        # Fallback:
        #   soil["raw_data"]
        #
        # This prevents the unified context from returning
        # Unknown when the soil collector already has district/state.
        ############################################################

        soil_location = soil.get(
            "location",
            {}
        )

        if not isinstance(soil_location, dict):
            soil_location = {}

        soil_raw = soil.get(
            "raw_data",
            {}
        )

        if not isinstance(soil_raw, dict):
            soil_raw = {}

        existing_location = data.get(
            "location",
            {}
        )

        if not isinstance(existing_location, dict):
            existing_location = {}

        district = (
            soil_location.get("district")
            or soil_raw.get("district")
            or existing_location.get("district")
            or "Unknown"
        )

        state = (
            soil_location.get("state")
            or soil_raw.get("state")
            or existing_location.get("state")
            or "Unknown"
        )

        ############################################################
        # Risks & Opportunities
        ############################################################

        risks = []
        opportunities = []

        ############################################################
        # Weather
        ############################################################

        risks.extend(
            weather["assessment"].get(
                "identified_risks",
                []
            )
        )

        ############################################################
        # Soil
        ############################################################

        if soil["assessment"]["soil_health_score"] >= 90:

            opportunities.append(
                "Excellent soil quality"
            )

        ############################################################
        # Satellite
        ############################################################

        vegetation_health = "Unknown"

        if satellite["status"] == "success":

            vegetation_health = satellite["vegetation"]["health"]

            if vegetation_health == "Critical":

                risks.append(
                    "Vegetation health is critical"
                )

            if satellite["water"]["stress"] == "High":

                risks.append(
                    "High crop water stress"
                )

            if satellite["soil"]["exposure"] == "High":

                risks.append(
                    "Large exposed soil area"
                )

        else:

            risks.append(
                "Satellite analysis unavailable"
            )

        ############################################################
        # Market
        ############################################################

        if (
            market["status"] == "success"
            and
            market["assessment"]["trend"] == "Increasing"
        ):

            opportunities.append(
                "Market prices increasing"
            )

        ############################################################
        # Historical
        ############################################################

        records = historical.get(
            "records",
            []
        )

        historical_similarity = historical.get(
            "similarity",
            0.0
        )

        if records:

            opportunities.append(
                f"{len(records)} historical records available"
            )

        else:

            risks.append(
                "No historical records available"
            )

        ############################################################
        # Confidence
        ############################################################

        confidence_scores = [

            weather.get("confidence", 0),

            soil.get("confidence", 0),

            market.get("confidence", 0)

        ]

        if satellite["status"] == "success":

            confidence_scores.append(
                satellite.get("confidence", 0)
            )

        confidence = sum(confidence_scores) / len(confidence_scores)

        ############################################################
        # Final Context
        ############################################################

        return {

            "crop": crop,

            "crop_profile": crop_profile,

            "location": {

                "district": district,

                "state": state

            },

            "weather": weather,

            "soil": soil,

            "satellite": satellite,

            "market": market,

            "historical": historical,

            "historical_records": len(records),

            "historical_similarity": round(
                historical_similarity,
                2
            ),

            "weather_status": weather["assessment"]["status"],

            "soil_health": soil["assessment"]["soil_health_score"],

            "vegetation_health": vegetation_health,

            "market_trend": market["assessment"].get(
                "trend",
                "Unknown"
            ),

            "risks": list(dict.fromkeys(risks)),

            "opportunities": list(dict.fromkeys(opportunities)),

            "confidence": round(confidence, 2)

        }


##########################################################################

context_agent = ContextAgent()