"""
==========================================================================
AgriMind

Confidence Explainer

Module 13U

Responsibilities
----------------
1. Calculate specialist confidence.
2. Incorporate evidence reliability.
3. Incorporate decision relevance.
4. Produce source-level confidence.
5. Identify strongest and weakest evidence.
6. Produce an explainable confidence breakdown.

Author : AgriMind Team
==========================================================================
"""


class ConfidenceExplainer:

    ####################################################################
    # Normalize Confidence
    ####################################################################

    def normalize(

        self,

        value

    ):

        try:

            value = float(

                value

            )

        except (

            TypeError,

            ValueError

        ):

            return 0.0

        if value > 1:

            value /= 100

        return max(

            0.0,

            min(

                value,

                1.0

            )

        )

    ####################################################################
    # Reliability
    ####################################################################

    def reliability(

        self,

        source,

        output

    ):

        metadata = output.get(

            "metadata",

            {}

        )

        status = output.get(

            "status",

            "unknown"

        )

        if status != "completed":

            return 0.0

        value = 1.0

        ############################################################
        # Synthetic datasets
        ############################################################

        if source in (

            "SoilAgent",

            "MarketAgent"

        ):

            source_text = str(

                metadata.get(

                    "source",

                    ""

                )

            ).lower()

            if "synthetic" in source_text:

                value *= 0.75

        ############################################################
        # Historical
        ############################################################

        if source == "HistoricalAgent":

            if metadata.get(

                "historical_available"

            ) is False:

                value *= 0.35

        ############################################################

        return value

    ####################################################################
    # Explain
    ####################################################################

    def explain(

        self,

        specialists,

        reasoning,

        executive_decision

    ):

        breakdown = {}

        weighted_values = []

        for source, output in specialists.items():

            confidence = self.normalize(

                output.get(

                    "confidence",

                    0

                )

            )

            reliability = self.reliability(

                source,

                output

            )

            score = (

                confidence

                * reliability

            )

            breakdown[source] = round(

                score,

                4

            )

            weighted_values.append(

                score

            )

        ############################################################
        # Reasoning
        ############################################################

        reasoning_confidence = self.normalize(

            getattr(

                reasoning,

                "confidence",

                0

            )

        )

        breakdown["CollaborativeReasoning"] = round(

            reasoning_confidence,

            4

        )

        weighted_values.append(

            reasoning_confidence

        )

        ############################################################
        # Executive
        ############################################################

        executive_confidence = self.normalize(

            executive_decision.get(

                "confidence",

                0

            )

        )

        breakdown["ExecutiveDecision"] = round(

            executive_confidence,

            4

        )

        weighted_values.append(

            executive_confidence

        )

        ############################################################
        # Average
        ############################################################

        overall = (

            sum(

                weighted_values

            )

            /

            len(

                weighted_values

            )

            if weighted_values

            else 0

        )

        ############################################################
        # Specialist average
        ############################################################

        specialist_values = [

            value

            for source, value in breakdown.items()

            if source not in (

                "CollaborativeReasoning",

                "ExecutiveDecision"

            )

        ]

        specialist_average = (

            sum(

                specialist_values

            )

            /

            len(

                specialist_values

            )

            if specialist_values

            else 0

        )

        ############################################################
        # Strongest / weakest
        ############################################################

        source_values = {

            source: value

            for source, value in breakdown.items()

            if source not in (

                "CollaborativeReasoning",

                "ExecutiveDecision"

            )

        }

        if source_values:

            strongest_source = max(

                source_values,

                key=source_values.get

            )

            weakest_source = min(

                source_values,

                key=source_values.get

            )

            strongest_confidence = source_values[

                strongest_source

            ]

            weakest_confidence = source_values[

                weakest_source

            ]

        else:

            strongest_source = ""

            weakest_source = ""

            strongest_confidence = 0

            weakest_confidence = 0

        ############################################################
        # Unavailable sources
        ############################################################

        unavailable_sources = [

            source

            for source, output in specialists.items()

            if output.get(

                "status"

            ) != "completed"

        ]

        ############################################################
        # Explanation
        ############################################################

        explanation = (

            f"Overall evidence confidence is "

            f"{overall:.2f}. "

            f"The strongest specialist evidence came from "

            f"{strongest_source or 'none'} "

            f"({strongest_confidence:.2f}), while the weakest was "

            f"{weakest_source or 'none'} "

            f"({weakest_confidence:.2f}). "

            "Source reliability and evidence provenance were considered "

            "alongside raw specialist confidence."

        )

        return {

            "overall":

                round(

                    overall,

                    4

                ),

            "specialist_average":

                round(

                    specialist_average,

                    4

                ),

            "strongest_source":

                strongest_source,

            "strongest_confidence":

                round(

                    strongest_confidence,

                    4

                ),

            "weakest_source":

                weakest_source,

            "weakest_confidence":

                round(

                    weakest_confidence,

                    4

                ),

            "unavailable_sources":

                unavailable_sources,

            "breakdown":

                breakdown,

            "confidence_explanation":

                explanation

        }


##########################################################################

confidence_explainer = ConfidenceExplainer()