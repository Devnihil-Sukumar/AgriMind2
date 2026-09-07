"""
==========================================================================
AgriMind

Context-Aware Alternative Generator

Module 13T

Responsibilities
----------------
1. Generate alternatives from the actual recommendation.
2. Use specialist evidence to make alternatives context-aware.
3. Explain expected outcomes.
4. Explain why alternatives were rejected.
5. Avoid generic alternatives when stronger contextual alternatives exist.

Author : AgriMind Team
==========================================================================
"""


class AlternativeGenerator:

    """
    Generates context-aware alternatives for explainability.
    """

    ####################################################################
    # Helper
    ####################################################################

    def add(

        self,

        alternatives,

        decision,

        expected_result,

        reason,

        context_signal=None

    ):

        if any(

            item["decision"].lower()
            == decision.lower()

            for item in alternatives

        ):

            return

        alternatives.append(

            {

                "decision":

                    decision,

                "expected_result":

                    expected_result,

                "why_rejected":

                    reason,

                "context_signal":

                    context_signal or ""

            }

        )

    ####################################################################
    # Extract Recommendation Text
    ####################################################################

    def get_recommendation_text(

        self,

        executive_decision,

        reasoning,
        context

    ):

        recommendation = executive_decision.get(

            "recommendation",

            ""

        )

        if not recommendation:

            recommendation = executive_decision.get(

                "decision",

                ""

            )

        if not recommendation:

            recommendation = getattr(

                reasoning,

                "summary",

                ""

            )

        return str(

            recommendation

        ).lower()

    ####################################################################
    # Irrigation Alternatives
    ####################################################################

    def irrigation_alternatives(

        self,

        alternatives,

        context,

        reasoning

    ):

        weather = context.get(

            "weather",

            {}

        )

        satellite = context.get(

            "satellite",

            {}

        )

        ############################################################
        # Current signals
        ############################################################

        rainfall = (

            weather.get(

                "raw_data",

                {}

            ).get(

                "rainfall"

            )

        )

        water_stress = (

            satellite.get(

                "water",

                {}

            ).get(

                "stress"

            )

        )

        ############################################################

        self.add(

            alternatives,

            "Delay irrigation",

            "The crop may remain under water stress for longer.",

            "Immediate irrigation was preferred because current evidence "

            "indicates insufficient water availability.",

            f"Rainfall={rainfall}, water_stress={water_stress}"

        )

        self.add(

            alternatives,

            "Apply partial irrigation",

            "Water demand may be reduced, but crop recovery may be slower.",

            "The evidence supports stronger intervention than a partial "

            "irrigation strategy.",

            f"Water stress={water_stress}"

        )

        self.add(

            alternatives,

            "Wait for natural rainfall",

            "Irrigation cost could be avoided if sufficient rainfall occurs.",

            "Current rainfall evidence does not provide enough support "

            "for waiting.",

            f"Current rainfall={rainfall}"

        )

    ####################################################################
    # Fertilizer Alternatives
    ####################################################################

    def fertilizer_alternatives(

        self,

        alternatives,

        context,

        reasoning

    ):

        soil = context.get(

            "soil",

            {}

        )

        raw_soil = soil.get(

            "raw_data",

            soil

        )

        nitrogen = raw_soil.get(

            "nitrogen",

            "Unknown"

        )

        organic = raw_soil.get(

            "organic_carbon",

            "Unknown"

        )

        ############################################################

        self.add(

            alternatives,

            "Delay fertilizer application",

            "Nutrient deficiency may persist or worsen.",

            "Current soil evidence indicates that nutrient management "

            "should not be unnecessarily delayed.",

            f"Nitrogen={nitrogen}, organic_carbon={organic}"

        )

        self.add(

            alternatives,

            "Apply a reduced fertilizer dose",

            "Lower cost and lower nutrient loading, but crop response "

            "may be weaker.",

            "The selected recommendation provides stronger correction "

            "for the identified nutrient condition.",

            f"Nitrogen={nitrogen}"

        )

        self.add(

            alternatives,

            "Take no nutrient action",

            "Existing nutrient limitations would remain unresolved.",

            "Soil evidence identifies a nutrient-related limitation.",

            f"Nitrogen={nitrogen}"

        )

    ####################################################################
    # Market Alternatives
    ####################################################################

    def market_alternatives(

        self,

        alternatives,

        context,

        reasoning

    ):

        market = context.get(

            "market",

            {}

        )

        top_markets = market.get(

            "top_markets",

            []

        )

        nearest = market.get(

            "nearest_market"

        )

        ############################################################

        best_market = (

            top_markets[0]

            if top_markets

            else None

        )

        ############################################################

        if best_market:

            best_name = best_market.get(

                "market",

                "best-ranked market"

            )

            best_price = best_market.get(

                "price",

                0

            )

            ########################################################

            self.add(

                alternatives,

                "Sell at the nearest market",

                "Transport cost may be lower, but the achievable price "

                "may also be lower.",

                "The selected market achieved a stronger composite score "

                "after considering price, trend, and distance.",

                f"Best market={best_name}, price={best_price}"

            )

        ############################################################

        self.add(

            alternatives,

            "Delay selling",

            "A future price increase could improve returns, but prices "

            "may also decline.",

            "Current market conditions provide a sufficiently favorable "

            "selling opportunity.",

            f"Top-market count={len(top_markets)}"

        )

        ############################################################

        self.add(

            alternatives,

            "Sell at the highest-price market regardless of distance",

            "Higher gross revenue may be offset by transport costs and "

            "operational difficulty.",

            "AgriMind considers market price together with geographic "

            "accessibility and market trend.",

            f"Candidate markets={len(top_markets)}"

        )

    ####################################################################
    # Harvest Alternatives
    ####################################################################

    def harvest_alternatives(

        self,

        alternatives,

        context,

        reasoning

    ):

        satellite = context.get(

            "satellite",

            {}

        )

        vegetation = satellite.get(

            "vegetation",

            {}

        )

        health = vegetation.get(

            "health",

            "Unknown"

        )

        ############################################################

        self.add(

            alternatives,

            "Delay harvest",

            "Crop may gain additional maturity, but quality or yield "

            "risk may increase depending on crop condition.",

            "Current evidence does not justify delaying the recommended "

            "harvest action.",

            f"Vegetation health={health}"

        )

        self.add(

            alternatives,

            "Partial harvest",

            "Some produce can be secured while the remainder continues "

            "maturing.",

            "A complete intervention is preferred under the current "

            "evidence pattern.",

            f"Vegetation health={health}"

        )

    ####################################################################
    # Disease / Crop Health Alternatives
    ####################################################################

    def disease_alternatives(

        self,

        alternatives,

        context,

        reasoning

    ):

        satellite = context.get(

            "satellite",

            {}

        )

        vegetation = satellite.get(

            "vegetation",

            {}

        )

        health = vegetation.get(

            "health",

            "Unknown"

        )

        ############################################################

        self.add(

            alternatives,

            "Observe before intervention",

            "The condition may progress before corrective action is taken.",

            "Observed vegetation stress warrants earlier intervention.",

            f"Vegetation health={health}"

        )

        ############################################################

        self.add(

            alternatives,

            "Apply treatment without inspection",

            "Treatment may address the wrong underlying cause.",

            "The decision process favors inspection before targeted "

            "intervention where the cause is uncertain.",

            "Evidence requires diagnostic confirmation"

        )

    ####################################################################
    # Generic Fallback Alternatives
    ####################################################################

    def generic_alternatives(

        self,

        alternatives,

        executive_decision

    ):

        decision = executive_decision.get(

            "decision",

            executive_decision.get(

                "executive_decision",

                "the selected action"

            )

        )

        ############################################################

        self.add(

            alternatives,

            "Take no immediate action",

            "Current risks may persist or worsen.",

            f"AgriMind selected '{decision}' because the available "

            "evidence supports intervention.",

            "No-action baseline"

        )

    ####################################################################
    # Generate
    ####################################################################

    def generate(

        self,

        executive_decision,

        reasoning,

        context

    ):

        recommendation = self.get_recommendation_text(

            executive_decision,

            reasoning,

            context

        )

        alternatives = []

        ############################################################
        # Crop
        ############################################################

        crop = str(

            context.get(

                "crop",

                context.get(

                    "crop_profile",

                    {}

                ).get(

                    "crop",

                    "crop"

                )

            )

        ).lower()

        ############################################################
        # Recommendation-specific alternatives
        ############################################################

        if (

            "irrigat" in recommendation

            or

            "water" in recommendation

        ):

            self.irrigation_alternatives(

                alternatives,

                context,

                reasoning

            )

        ############################################################

        if (

            "fertilizer" in recommendation

            or

            "nutrient" in recommendation

            or

            "nitrogen" in recommendation

        ):

            self.fertilizer_alternatives(

                alternatives,

                context,

                reasoning

            )

        ############################################################

        if (

            "sell" in recommendation

            or

            "market" in recommendation

            or

            "price" in recommendation

        ):

            self.market_alternatives(

                alternatives,

                context,

                reasoning

            )

        ############################################################

        if "harvest" in recommendation:

            self.harvest_alternatives(

                alternatives,

                context,

                reasoning

            )

        ############################################################

        if (

            "disease" in recommendation

            or

            "inspect" in recommendation

            or

            "health" in recommendation

        ):

            self.disease_alternatives(

                alternatives,

                context,

                reasoning

            )

        ############################################################
        # Fallback
        ############################################################

        self.generic_alternatives(

            alternatives,

            executive_decision

        )

        ############################################################
        # Limit
        ############################################################

        return alternatives[:6]

    ####################################################################
    # Summary
    ####################################################################

    def summarize(

        self,

        alternatives

    ):

        return [

            item["decision"]

            for item in alternatives

        ]


##########################################################################

alternative_generator = AlternativeGenerator()