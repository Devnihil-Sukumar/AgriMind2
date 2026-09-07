"""
==========================================================================
AgriMind

Soil Tool

Prefers LIVE measured soil from ISRIC SoilGrids, falling back to the
synthetic Tamil Nadu dataset when SoilGrids has no data for the
location or is unreachable.

SoilGrids masks built-up land, so a null response is a legitimate
answer rather than an error -- Coimbatore city centre returns nothing
while farmland 20km south returns pH 7.4. Both paths produce an
identical output schema; only `live_source` and `metadata.source`
differ, so downstream agents and the evaluation can tell measured data
from synthetic without any other change.

Responsibilities
----------------
1. Query SoilGrids for measured soil properties.
2. Fall back to the local dataset on a coverage gap or outage.
3. Extract soil properties.
4. Assess soil against crop profile.
5. Return standardized soil data.

Author : AgriMind Team
==========================================================================
"""

import logging
import math
import os

import pandas as pd

from app.services.soilgrids_service import soilgrids_service

logger = logging.getLogger(__name__)

##########################################################################
# Set SOIL_LIVE_SOURCE=0 to force the synthetic dataset -- used when
# reproducing a run whose soil figures came from the CSV.
##########################################################################

USE_LIVE_SOIL = os.getenv(
    "SOIL_LIVE_SOURCE",
    "1"
).strip().lower() not in ("0", "false", "no")


class SoilTool:

    ####################################################################
    # Constructor
    ####################################################################

    def __init__(self):

        self.df = pd.read_csv(

            "data/soil_data.csv"

        )

        self.df.columns = (

            self.df.columns

            .str.strip()

            .str.lower()

        )

    ####################################################################
    # Haversine
    ####################################################################

    def haversine(

        self,

        latitude_1,

        longitude_1,

        latitude_2,

        longitude_2

    ):

        radius = 6371.0

        lat1 = math.radians(

            float(latitude_1)

        )

        lat2 = math.radians(

            float(latitude_2)

        )

        dlat = math.radians(

            float(latitude_2)

            -

            float(latitude_1)

        )

        dlon = math.radians(

            float(longitude_2)

            -

            float(longitude_1)

        )

        value = (

            math.sin(dlat / 2) ** 2

            +

            math.cos(lat1)

            * math.cos(lat2)

            * math.sin(dlon / 2) ** 2

        )

        return (

            2

            * radius

            * math.asin(

                math.sqrt(value)

            )

        )

    ####################################################################
    # Classify Nitrogen
    ####################################################################

    def classify_nitrogen(

        self,

        nitrogen

    ):

        if isinstance(

            nitrogen,

            str

        ):

            return nitrogen.title()

        value = float(

            nitrogen

        )

        if value < 0.15:

            return "Low"

        if value < 0.30:

            return "Medium"

        return "High"

    ####################################################################
    # Classify Organic Carbon
    ####################################################################

    def classify_organic_carbon(

        self,

        organic_carbon

    ):

        if isinstance(

            organic_carbon,

            str

        ):

            return organic_carbon.title()

        value = float(

            organic_carbon

        )

        if value < 1.0:

            return "Low"

        if value < 2.0:

            return "Medium"

        return "High"

    ####################################################################
    # Find Nearest Soil
    ####################################################################

    def get_local_soil(

        self,

        latitude,

        longitude

    ):

        df = self.df.copy()

        df["distance_km"] = df.apply(

            lambda row:

                self.haversine(

                    latitude,

                    longitude,

                    row["latitude"],

                    row["longitude"]

                ),

            axis=1

        )

        nearest = df.sort_values(

            "distance_km"

        ).iloc[0]

        return {

            "state":

                str(

                    nearest["state"]

                ),

            "district":

                str(

                    nearest["district"]

                ),

            "latitude":

                float(

                    nearest["latitude"]

                ),

            "longitude":

                float(

                    nearest["longitude"]

                ),

            "ph":

                float(

                    nearest["ph"]

                ),

            "nitrogen":

                str(

                    nearest["nitrogen"]

                ),

            "organic_carbon":

                str(

                    nearest["organic_carbon"]

                ),

            "sand_percent":

                float(

                    nearest["sand"]

                ),

            "clay_percent":

                float(

                    nearest["clay"]

                ),

            "silt_percent":

                float(

                    nearest["silt"]

                ),

            "cec":

                float(

                    nearest["cec"]

                ),

            "bulk_density":

                float(

                    nearest["bulk_density"]

                ),

            "field_capacity":

                float(

                    nearest["field_capacity"]

                ),

            "wilting_point":

                float(

                    nearest["wilting_point"]

                ),

            "distance_km":

                float(

                    round(

                        nearest["distance_km"],

                        2

                    )

                ),

            "live_source":

                False

        }

    ####################################################################
    # Live Soil (SoilGrids)
    ####################################################################

    def get_live_soil(
        self,
        latitude,
        longitude
    ):
        """Measured soil from SoilGrids, mapped onto the same schema
        get_local_soil() returns. None means SoilGrids had nothing for
        this point (coverage gap) or was unreachable, and the caller
        should fall back.

        State/district still come from the nearest local record --
        SoilGrids is a raster with no administrative boundaries, and
        those two fields are geography, not soil measurements.
        """

        measured = soilgrids_service.fetch(
            latitude,
            longitude
        )

        if not measured:
            return None

        nearest = self.get_local_soil(
            latitude,
            longitude
        )

        return {

            "state": nearest["state"],

            "district": nearest["district"],

            "latitude": float(latitude),

            "longitude": float(longitude),

            "ph": measured["ph"],

            ##########################################################
            # SoilGrids reports continuous values; AgriMind's crop
            # profiles compare against Low/Medium/High bands, so reuse
            # the existing classifiers rather than inventing new ones.
            ##########################################################

            "nitrogen": self.classify_nitrogen(
                measured["nitrogen_percent"]
            ),

            "organic_carbon": self.classify_organic_carbon(
                measured["organic_carbon_percent"]
            ),

            "nitrogen_percent": measured["nitrogen_percent"],

            "organic_carbon_percent": measured["organic_carbon_percent"],

            "sand_percent": measured["sand_percent"],

            "clay_percent": measured["clay_percent"],

            "silt_percent": measured["silt_percent"],

            "cec": measured["cec"],

            "bulk_density": measured["bulk_density"],

            ##########################################################
            # Derived by pedotransfer, not measured -- see
            # soilgrids_service.estimate_water_retention().
            ##########################################################

            "field_capacity": measured["field_capacity"],

            "wilting_point": measured["wilting_point"],

            "distance_km": 0.0,

            "live_source": True

        }

    ####################################################################
    # Assess Soil
    ####################################################################

    def assess_soil(

        self,

        soil,

        crop_profile

    ):

        profile = crop_profile.get(

            "soil",

            {}

        )

        optimal = crop_profile.get(

            "optimal_conditions",

            {}

        )

        risks = []

        opportunities = []

        score = 100

        ph = soil.get(

            "ph"

        )

        nitrogen = str(

            soil.get(

                "nitrogen",

                "Unknown"

            )

        ).title()

        organic = str(

            soil.get(

                "organic_carbon",

                "Unknown"

            )

        ).title()

        sand = float(

            soil.get(

                "sand_percent",

                0

            )

        )

        clay = float(

            soil.get(

                "clay_percent",

                0

            )

        )

        ############################################################
        # pH
        ############################################################

        ph_range = optimal.get(

            "soil_ph",

            {}

        )

        ph_min = ph_range.get(

            "minimum"

        )

        ph_max = ph_range.get(

            "maximum"

        )

        if (

            ph is not None

            and ph_min is not None

            and ph_max is not None

        ):

            if ph_min <= ph <= ph_max:

                opportunities.append(

                    "Soil pH is within the optimal range."

                )

            else:

                risks.append(

                    f"Soil pH ({ph}) is outside the optimal range."

                )

                score -= 20

        ############################################################
        # Nitrogen
        ############################################################

        preferred_nitrogen = str(

            profile.get(

                "preferred_nitrogen",

                ""

            )

        ).title()

        levels = {

            "Low": 1,

            "Medium": 2,

            "High": 3

        }

        if (

            preferred_nitrogen

            and nitrogen in levels

        ):

            if levels[nitrogen] >= levels.get(

                preferred_nitrogen,

                2

            ):

                opportunities.append(

                    "Nitrogen level matches crop requirement."

                )

            else:

                risks.append(

                    "Nitrogen level is below crop requirement."

                )

                score -= 10

        ############################################################
        # Organic Carbon
        ############################################################

        preferred_organic = str(

            profile.get(

                "preferred_organic_carbon",

                ""

            )

        ).title()

        if (

            preferred_organic

            and organic in levels

        ):

            if levels[organic] >= levels.get(

                preferred_organic,

                2

            ):

                opportunities.append(

                    "Organic carbon matches crop requirement."

                )

            else:

                risks.append(

                    "Organic carbon is below crop requirement."

                )

                score -= 10

        ############################################################
        # Texture
        ############################################################

        preferred_texture = [

            str(x).lower()

            for x in profile.get(

                "preferred_texture",

                []

            )

        ]

        texture = self.infer_texture(

            sand,

            clay

        )

        if preferred_texture:

            if any(

                p in texture.lower()

                for p in preferred_texture

            ):

                opportunities.append(

                    "Soil texture is suitable."

                )

            else:

                risks.append(

                    f"Soil texture ({texture}) differs from preferred soil."

                )

                score -= 10

        score = max(

            min(

                score,

                100

            ),

            0

        )

        return {

            "soil_health_score":

                score,

            "ph_status":

                "Optimal"

                if not any(

                    "pH" in risk

                    for risk in risks

                )

                else "Suboptimal",

            "nitrogen_status":

                nitrogen,

            "organic_carbon_status":

                organic,

            "texture":

                texture,

            "risks":

                risks,

            "opportunities":

                opportunities,

            "live_source":

                False,

            "live_confidence":

                0

        }

    ####################################################################
    # Texture
    ####################################################################

    def infer_texture(

        self,

        sand,

        clay

    ):

        if clay >= 35:

            return "Clay"

        if sand >= 50 and clay < 25:

            return "Sandy Loam"

        if clay >= 27:

            return "Clay Loam"

        return "Loam"

    ####################################################################
    # Execute
    ####################################################################

    def execute(

        self,

        crop_profile,

        latitude,

        longitude

    ):

        soil = None

        if USE_LIVE_SOIL:

            try:

                soil = self.get_live_soil(

                    latitude,

                    longitude

                )

            except Exception as error:

                ##################################################
                # A live-source problem must never fail the whole
                # soil stage -- the synthetic dataset is always
                # available underneath.
                ##################################################

                logger.warning(
                    "SoilGrids lookup failed, falling back to local "
                    "dataset: %s",
                    error
                )

                soil = None

        if soil is None:

            soil = self.get_local_soil(

                latitude,

                longitude

            )

        assessment = self.assess_soil(

            soil,

            crop_profile

        )

        live = bool(
            soil.get("live_source")
        )

        assessment["live_source"] = live

        assessment["live_confidence"] = 1 if live else 0

        return {

            "agent":

                "soil_tool",

            "status":

                "success",

            "confidence":

                round(

                    assessment["soil_health_score"]

                    / 100,

                    2

                ),

            "data":

                soil,

            "assessment":

                assessment,

            "metadata": {

                "source":

                    "ISRIC SoilGrids v2.0 (measured)"
                    if live
                    else "Synthetic Local Dataset",

                "distance_km":

                    soil["distance_km"],

                "live_source":

                    live,

                "water_retention":

                    "derived (Saxton & Rawls 2006 pedotransfer)"
                    if live
                    else "dataset value"

            }

        }


##########################################################################

soil_tool = SoilTool()