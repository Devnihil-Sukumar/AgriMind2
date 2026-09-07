"""
==========================================================================
AgriMind

Runtime-Aware Limitation Generator

Module 13S

Responsibilities
----------------
1. Inspect actual runtime conditions.
2. Detect unavailable or degraded evidence.
3. Detect synthetic/local data usage.
4. Detect low-confidence specialist outputs.
5. Detect satellite quality limitations.
6. Detect historical-data limitations.
7. Detect market-data limitations.
8. Detect cross-agent conflicts.
9. Return only execution-specific limitations.

Author : AgriMind Team
==========================================================================
"""


class LimitationGenerator:

    """
    Generates limitations from actual execution state.
    """

    ####################################################################
    # Add Limitation
    ####################################################################

    def _add(

        self,

        limitations,

        category,

        message,

        impact,

        evidence=None

    ):

        limitations.append(

            {

                "category":

                    category,

                "limitation":

                    message,

                "impact":

                    impact,

                "evidence":

                    evidence or ""

            }

        )

    ####################################################################
    # Specialist Availability
    ####################################################################

    def _check_specialist_availability(

        self,

        limitations,

        specialists

    ):

        expected_agents = [

            "WeatherAgent",

            "SoilAgent",

            "SatelliteAgent",

            "MarketAgent",

            "HistoricalAgent"

        ]

        for agent_name in expected_agents:

            if agent_name not in specialists:

                self._add(

                    limitations,

                    "Missing Evidence",

                    f"{agent_name} did not return an output.",

                    "The final recommendation was produced without "

                    f"{agent_name} evidence.",

                    agent_name

                )

                continue

            output = specialists.get(

                agent_name,

                {}

            )

            status = output.get(

                "status",

                "unknown"

            )

            if status != "completed":

                self._add(

                    limitations,

                    "Failed Evidence",

                    f"{agent_name} did not complete successfully.",

                    "Its evidence could not be used reliably in the "

                    "decision process.",

                    str(

                        output.get(

                            "error",

                            "Unknown failure"

                        )

                    )

                )

    ####################################################################
    # Confidence Limitations
    ####################################################################

    def _check_confidence(

        self,

        limitations,

        specialists

    ):

        for agent_name, output in specialists.items():

            confidence = output.get(

                "confidence"

            )

            if confidence is None:

                continue

            try:

                confidence = float(

                    confidence

                )

            except (

                TypeError,

                ValueError

            ):

                continue

            if confidence < 0.50:

                self._add(

                    limitations,

                    "Low Confidence",

                    f"{agent_name} reported low confidence "

                    f"({confidence:.2f}).",

                    "Its evidence should be treated cautiously when "

                    "interpreting the final recommendation.",

                    f"confidence={confidence:.2f}"

                )

            elif confidence < 0.70:

                self._add(

                    limitations,

                    "Moderate Confidence",

                    f"{agent_name} reported moderate confidence "

                    f"({confidence:.2f}).",

                    "Its evidence may influence the decision, but should "

                    "not be treated as highly certain.",

                    f"confidence={confidence:.2f}"

                )

    ####################################################################
    # Soil Limitations
    ####################################################################

    def _check_soil(

        self,

        limitations,

        context

    ):

        soil = context.get(

            "soil",

            {}

        )

        if not soil:

            self._add(

                limitations,

                "Soil",

                "No soil information was available during this run.",

                "Soil-related evidence could not contribute to the "

                "recommendation."

            )

            return

        raw = soil.get(

            "raw_data",

            soil

        )

        source = str(

            raw.get(

                "source",

                ""

            )

        ).lower()

        live_source = raw.get(

            "live_source",

            False

        )

        if (

            live_source is False

            or

            "synthetic" in source

            or

            "local" in source

        ):

            self._add(

                limitations,

                "Soil Data Provenance",

                "Soil analysis used the local synthetic/scenario-controlled "

                "dataset rather than live field measurements.",

                "The soil assessment is suitable for controlled system "

                "evaluation but should not be interpreted as a direct "

                "measurement of the current field.",

                source or "local dataset"

            )

        distance = raw.get(

            "distance_km"

        )

        if distance is not None:

            try:

                distance = float(

                    distance

                )

                if distance > 25:

                    self._add(

                        limitations,

                        "Spatial Representativeness",

                        f"The nearest soil record is approximately "

                        f"{distance:.1f} km from the farm coordinates.",

                        "The soil observation may not fully represent "

                        "conditions at the exact farm location.",

                        f"distance_km={distance:.1f}"

                    )

            except (

                TypeError,

                ValueError

            ):

                pass

    ####################################################################
    # Market Limitations
    ####################################################################

    def _check_market(

        self,

        limitations,

        context

    ):

        market = context.get(

            "market",

            {}

        )

        if not market:

            self._add(

                limitations,

                "Market Data",

                "No market information was available during this run.",

                "Market conditions could not be considered in the "

                "recommendation."

            )

            return

        source = str(

            market.get(

                "metadata",

                {}

            ).get(

                "source",

                market.get(

                    "source",

                    ""

                )

            )

        ).lower()

        if (

            "synthetic" in source

            or

            "local" in source

        ):

            self._add(

                limitations,

                "Market Data Provenance",

                "Market analysis used the synthetic local market dataset.",

                "The ranking is valid for controlled testing but should "

                "not be interpreted as real-time market intelligence.",

                source

            )

        top_markets = market.get(

            "top_markets",

            []

        )

        if not top_markets:

            self._add(

                limitations,

                "Market Ranking",

                "No ranked nearby markets were available.",

                "Market comparison and geographic ranking could not "

                "be performed."

            )

    ####################################################################
    # Satellite Limitations
    ####################################################################

    def _check_satellite(

        self,

        limitations,

        context

    ):

        satellite = context.get(

            "satellite",

            {}

        )

        if not satellite:

            self._add(

                limitations,

                "Satellite",

                "No satellite observation was available.",

                "Vegetation, water-stress, and exposed-soil evidence "

                "could not be directly assessed."

            )

            return

        imagery = satellite.get(

            "imagery",

            {}

        )

        cloud_cover = imagery.get(

            "cloud_cover"

        )

        if cloud_cover is not None:

            try:

                cloud_cover = float(

                    cloud_cover

                )

                if cloud_cover >= 50:

                    self._add(

                        limitations,

                        "Satellite Quality",

                        f"Satellite imagery had high cloud cover "

                        f"({cloud_cover:.1f}%).",

                        "Vegetation indices may be less representative "

                        "because of reduced image quality.",

                        f"cloud_cover={cloud_cover:.1f}%"

                    )

                elif cloud_cover >= 30:

                    self._add(

                        limitations,

                        "Satellite Quality",

                        f"Satellite imagery had moderate cloud cover "

                        f"({cloud_cover:.1f}%).",

                        "Some vegetation measurements may contain greater "

                        "uncertainty than under clear-sky conditions.",

                        f"cloud_cover={cloud_cover:.1f}%"

                    )

            except (

                TypeError,

                ValueError

            ):

                pass

        valid_pixels = imagery.get(

            "valid_pixels"

        )

        if valid_pixels is not None:

            try:

                valid_pixels = float(

                    valid_pixels

                )

                if valid_pixels < 70:

                    self._add(

                        limitations,

                        "Satellite Coverage",

                        f"Only {valid_pixels:.1f}% of image pixels were "

                        "valid for analysis.",

                        "The satellite assessment may not represent the "

                        "entire farm area reliably.",

                        f"valid_pixels={valid_pixels:.1f}%"

                    )

            except (

                TypeError,

                ValueError

            ):

                pass

    ####################################################################
    # Historical Limitations
    ####################################################################

    def _check_historical(

        self,

        limitations,

        context,

        specialists

    ):

        historical = context.get(

            "historical",

            {}

        )

        agent = specialists.get(

            "HistoricalAgent",

            {}

        )

        metadata = agent.get(

            "metadata",

            {}

        )

        available = metadata.get(

            "historical_available"

        )

        if available is False:

            self._add(

                limitations,

                "Historical Evidence",

                "No comparable historical farm records were available.",

                "The system could not validate the recommendation "

                "against previous seasons or farm outcomes.",

                "historical_available=False"

            )

            return

        if not historical:

            self._add(

                limitations,

                "Historical Evidence",

                "Historical records were unavailable for this run.",

                "Temporal comparison and recurrence analysis were limited."

            )

    ####################################################################
    # Conflict Detection
    ####################################################################

    def _check_conflicts(

        self,

        limitations,

        reasoning

    ):

        merged_risks = getattr(

            reasoning,

            "merged_risks",

            []

        )

        merged_opportunities = getattr(

            reasoning,

            "merged_opportunities",

            []

        )

        if not merged_risks or not merged_opportunities:

            return

        risk_text = " ".join(

            str(

                item

            ).lower()

            for item in merged_risks

        )

        opportunity_text = " ".join(

            str(

                item

            ).lower()

            for item in merged_opportunities

        )

        conflicting_pairs = [

            (

                [

                    "increasing",

                    "decreasing"

                ],

                "market trend"

            ),

            (

                [

                    "water stress",

                    "water sufficient"

                ],

                "water availability"

            ),

            (

                [

                    "critical",

                    "optimal"

                ],

                "condition status"

            )

        ]

        for keywords, label in conflicting_pairs:

            if all(

                keyword in risk_text + opportunity_text

                for keyword in keywords

            ):

                self._add(

                    limitations,

                    "Evidence Conflict",

                    f"Conflicting evidence was detected for {label}.",

                    "The final decision may be sensitive to how conflicting "

                    "evidence was weighted.",

                    label

                )

    ####################################################################
    # Generate
    ####################################################################

    def generate(

        self,

        specialists,

        reasoning,

        executive_decision,

        context

    ):

        limitations = []

        ############################################################
        # Data availability
        ############################################################

        self._check_specialist_availability(

            limitations,

            specialists

        )

        ############################################################
        # Confidence
        ############################################################

        self._check_confidence(

            limitations,

            specialists

        )

        ############################################################
        # Soil
        ############################################################

        self._check_soil(

            limitations,

            context

        )

        ############################################################
        # Market
        ############################################################

        self._check_market(

            limitations,

            context

        )

        ############################################################
        # Satellite
        ############################################################

        self._check_satellite(

            limitations,

            context

        )

        ############################################################
        # Historical
        ############################################################

        self._check_historical(

            limitations,

            context,

            specialists

        )

        ############################################################
        # Conflicts
        ############################################################

        self._check_conflicts(

            limitations,

            reasoning

        )

        ############################################################
        # No limitation
        ############################################################

        if not limitations:

            limitations.append(

                {

                    "category":

                        "Runtime Status",

                    "limitation":

                        "No significant runtime limitations were detected.",

                    "impact":

                        "The available evidence was sufficiently complete "

                        "for this execution.",

                    "evidence":

                        "All expected specialist outputs were available."

                }

            )

        return limitations


##########################################################################

limitation_generator = LimitationGenerator()