"""
==========================================================================
AgriMind

Market Specialist Agent

Module 13Q

Responsibilities
----------------
1. Analyze current market conditions.
2. Compare with crop market profile.
3. Analyze nearest and top-ranked markets.
4. Detect selling opportunities.
5. Detect market risks.
6. Generate a deterministic specialist summary.

Author : AgriMind Team
==========================================================================
"""

import json

from app.agents.base_agent import BaseAgent
from app.utils.json_extract import extract_json_object
from app.prompts.market_prompt import MARKET_PROMPT


class MarketAgent(BaseAgent):

    """
    Market Specialist Agent
    """

    name = "MarketAgent"
    component = "market"
    # No documented model-specific failure here (unlike SatelliteAgent's
    # provider override -- see that file's comment), so this respects
    # MARKET_LLM_PROVIDER in .env instead of hardcoding a provider that
    # requires an API key this deployment doesn't have.

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context

    ):

        crop_profile = context["crop_profile"]

        market = context["market"]

        prompt = f"""
{MARKET_PROMPT}

============================================================

CROP PROFILE

{json.dumps(
    crop_profile,
    indent=4,
    default=str
)}

============================================================

CURRENT MARKET DATA

{json.dumps(
    market,
    indent=4,
    default=str
)}

============================================================

TASK

Analyze the CURRENT MARKET CONDITIONS against the CROP PROFILE.

Evaluate

1. Current market trend.
2. Nearest market.
3. Best-ranked market.
4. Top 5 market opportunities.
5. Current selling opportunity.
6. Market risks.
7. Market opportunities.
8. Harvest timing.
9. Whether selling now is recommended.
10. Overall market assessment.

Return ONLY valid JSON.

Schema

{{
    "analysis": "",
    "risks": [],
    "opportunities": [],
    "confidence": 0.95
}}

"""

        return prompt

    ####################################################################
    # Parse Response
    ####################################################################

    def parse_response(

        self,

        response

    ):

        ########################################################
        # Escape-aware extraction.
        #
        # openai/gpt-oss-120b is a reasoning model and can emit
        # commentary around the JSON body. A naive find("{")/
        # rfind("}") slice grabs the LAST brace in the WHOLE
        # response, which can belong to unrelated trailing text and
        # produce an unparseable slice. This shares BaseAgent's
        # escape-aware brace matching instead.
        ########################################################

        result = extract_json_object(

            response,

            error_label="MarketAgent"

        )

        analysis = str(

            result.get(

                "analysis",

                ""

            )

        ).strip()

        risks = result.get(

            "risks",

            []

        )

        opportunities = result.get(

            "opportunities",

            []

        )

        confidence = float(

            result.get(

                "confidence",

                0

            )

        )

        ################################################################
        # Deterministic Specialist Summary
        ################################################################

        market_context = self._last_context_market

        top_markets = market_context.get(

            "top_markets",

            []

        )

        nearest = market_context.get(

            "nearest_market"

        )

        summary_parts = []

        if nearest:

            summary_parts.append(

                "Nearest market: "

                f"{nearest.get('market', 'Unknown')} "

                f"({nearest.get('distance_km', 0)} km)."

            )

        if top_markets:

            best = top_markets[0]

            summary_parts.append(

                "Best-ranked market: "

                f"{best.get('market', 'Unknown')} "

                f"with modal price "

                f"{best.get('price', 0)}."

            )

            summary_parts.append(

                f"{len(top_markets)} market(s) were evaluated."

            )

        if analysis:

            summary_parts.append(

                analysis

            )

        if risks:

            summary_parts.append(

                f"{len(risks)} market risk(s) identified."

            )

        if opportunities:

            summary_parts.append(

                f"{len(opportunities)} market opportunity(s) identified."

            )

        if not summary_parts:

            summary_parts.append(

                "No significant market findings were returned."

            )

        summary = " ".join(

            summary_parts

        )

        result["agent"] = self.name

        result["status"] = "completed"

        result["summary"] = summary

        result["analysis"] = analysis

        result["risks"] = risks

        result["opportunities"] = opportunities

        result["confidence"] = confidence

        ################################################################
        # Market metadata
        ################################################################

        result["metadata"] = {

            "nearest_market":

                nearest,

            "top_market_count":

                len(top_markets),

            "top_markets":

                top_markets

        }

        return result

    ####################################################################
    # Build Prompt Override
    ####################################################################

    def execute(

        self,

        context

    ):

        self._last_context_market = context.get(

            "market",

            {}

        )

        return super().execute(

            context

        )


##########################################################################

market_agent = MarketAgent()