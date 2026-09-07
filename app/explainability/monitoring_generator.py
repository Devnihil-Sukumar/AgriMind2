"""
==========================================================================
AgriMind

Monitoring Generator

Module 5G

Responsibilities
----------------
1. Generate monitoring recommendations.
2. Prioritize follow-up observations.
3. Suggest monitoring frequency.
4. Support explainable recommendations.

Author : AgriMind Team
==========================================================================
"""


class MonitoringGenerator:

    """
    Generates post-recommendation monitoring plans.
    """

    ####################################################################
    # Generate Monitoring Plan
    ####################################################################

    def generate(

        self,

        specialists,

        executive_decision,

        recommendation,

        context

    ):

        monitoring = []

        ############################################################
        # Weather
        ############################################################

        weather = specialists.get(

            "WeatherAgent",

            {}

        )

        monitoring.append(

            {

                "source":

                    "Weather",

                "parameter":

                    "Rainfall Forecast",

                "frequency":

                    "Daily",

                "reason":

                    "Weather changes can affect irrigation and field operations."

            }

        )

        monitoring.append(

            {

                "source":

                    "Weather",

                "parameter":

                    "Temperature & Humidity",

                "frequency":

                    "Daily",

                "reason":

                    "Monitor environmental stress."

            }

        )

        ############################################################
        # Soil
        ############################################################

        soil = specialists.get(

            "SoilAgent",

            {}

        )

        monitoring.append(

            {

                "source":

                    "Soil",

                "parameter":

                    "Soil Moisture",

                "frequency":

                    "Every 2 Days",

                "reason":

                    "Ensure irrigation is effective."

            }

        )

        monitoring.append(

            {

                "source":

                    "Soil",

                "parameter":

                    "Soil pH",

                "frequency":

                    "Monthly",

                "reason":

                    "Maintain suitable soil conditions."

            }

        )

        ############################################################
        # Satellite
        ############################################################

        monitoring.append(

            {

                "source":

                    "Satellite",

                "parameter":

                    "NDVI",

                "frequency":

                    "Weekly",

                "reason":

                    "Monitor vegetation health."

            }

        )

        monitoring.append(

            {

                "source":

                    "Satellite",

                "parameter":

                    "NDWI",

                "frequency":

                    "Weekly",

                "reason":

                    "Detect crop water stress."

            }

        )

        ############################################################
        # Market
        ############################################################

        monitoring.append(

            {

                "source":

                    "Market",

                "parameter":

                    "Crop Price",

                "frequency":

                    "Daily",

                "reason":

                    "Identify the best selling opportunity."

            }

        )

        ############################################################
        # Historical
        ############################################################

        monitoring.append(

            {

                "source":

                    "Historical",

                "parameter":

                    "Seasonal Comparison",

                "frequency":

                    "Monthly",

                "reason":

                    "Compare current performance with previous seasons."

            }

        )

        ############################################################
        # Recommendation-specific monitoring
        ############################################################

        text = recommendation.get(

            "recommendation",

            ""

        ).lower()

        ############################################################

        if "irrig" in text:

            monitoring.append(

                {

                    "source":

                        "Recommendation",

                    "parameter":

                        "Irrigation Effectiveness",

                    "frequency":

                        "After Every Irrigation",

                    "reason":

                        "Confirm reduction in crop water stress."

                }

            )

        ############################################################

        if "fertilizer" in text:

            monitoring.append(

                {

                    "source":

                        "Recommendation",

                    "parameter":

                        "Leaf Nutrient Status",

                    "frequency":

                        "Weekly",

                    "reason":

                        "Evaluate fertilizer response."

                }

            )

        ############################################################

        if "disease" in text:

            monitoring.append(

                {

                    "source":

                        "Recommendation",

                    "parameter":

                        "Disease Symptoms",

                    "frequency":

                        "Daily",

                    "reason":

                        "Early disease detection."

                }

            )

        ############################################################

        monitoring.append(

            {

                "source":

                    "System",

                "parameter":

                    "Overall Farm Health",

                "frequency":

                    "Weekly",

                "reason":

                    "Validate AgriMind recommendations."

            }

        )

        ############################################################

        return monitoring

    ####################################################################
    # Summary
    ####################################################################

    def summarize(

        self,

        monitoring

    ):

        return [

            f"{item['parameter']} ({item['frequency']})"

            for item in monitoring

        ]


##########################################################################

monitoring_generator = MonitoringGenerator()