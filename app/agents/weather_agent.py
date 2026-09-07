"""
==========================================================================
AgriMind

Weather Specialist Agent

Module 13Q

Responsibilities
----------------
1. Analyze live weather conditions.
2. Compare with crop-specific optimal conditions.
3. Identify weather risks.
4. Identify weather opportunities.
5. Generate a deterministic specialist summary.

Author : AgriMind Team
==========================================================================
"""

import json

from app.agents.base_agent import BaseAgent
from app.utils.json_extract import extract_json_object
from app.prompts.weather_prompt import WEATHER_PROMPT


class WeatherAgent(BaseAgent):

    """
    Weather Specialist Agent
    """

    name = "WeatherAgent"
    component = "weather"
    provider = "ollama"

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context

    ):

        crop_profile = context["crop_profile"]

        weather = context["weather"]

        prompt = f"""
{WEATHER_PROMPT}

============================================================

CROP PROFILE

{json.dumps(
    crop_profile,
    indent=4,
    default=str
)}

============================================================

CURRENT WEATHER

{json.dumps(
    weather,
    indent=4,
    default=str
)}

============================================================

TASK

Compare the CURRENT WEATHER against the CROP PROFILE.

Determine

1. Whether the current weather is suitable.
2. Weather-related risks.
3. Weather-related opportunities.
4. A concise weather assessment.
5. Confidence score.

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

            error_label="WeatherAgent"

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

        summary_parts = []

        if analysis:

            summary_parts.append(

                analysis

            )

        if risks:

            summary_parts.append(

                f"{len(risks)} weather risk(s) identified."

            )

        if opportunities:

            summary_parts.append(

                f"{len(opportunities)} weather opportunity(s) identified."

            )

        if not summary_parts:

            summary_parts.append(

                "No significant weather findings were returned."

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

        return result


##########################################################################

weather_agent = WeatherAgent()