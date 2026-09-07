"""
==========================================================================
AgriMind

Soil Specialist Agent

Module 13Q

Responsibilities
----------------
1. Analyze current soil health.
2. Compare with crop requirements.
3. Identify nutrient deficiencies.
4. Identify soil opportunities.
5. Generate a deterministic specialist summary.

Author : AgriMind Team
==========================================================================
"""

import json

from app.agents.base_agent import BaseAgent
from app.utils.json_extract import extract_json_object
from app.prompts.soil_prompt import SOIL_PROMPT


class SoilAgent(BaseAgent):

    """
    Soil Specialist Agent
    """

    name = "SoilAgent"
    component = "soil"
    provider = "ollama"

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context

    ):

        crop_profile = context["crop_profile"]

        soil = context["soil"]

        prompt = f"""
{SOIL_PROMPT}

============================================================

CROP PROFILE

{json.dumps(
    crop_profile,
    indent=4,
    default=str
)}

============================================================

CURRENT SOIL DATA

{json.dumps(
    soil,
    indent=4,
    default=str
)}

============================================================

TASK

Compare the CURRENT SOIL CONDITIONS against the CROP PROFILE.

Evaluate

1. Soil suitability.
2. Soil pH.
3. Nitrogen status.
4. Organic carbon.
5. Soil texture.
6. Soil-related risks.
7. Soil-related opportunities.
8. Overall soil assessment.

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

            error_label="SoilAgent"

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

                f"{len(risks)} soil risk(s) identified."

            )

        if opportunities:

            summary_parts.append(

                f"{len(opportunities)} soil opportunity(s) identified."

            )

        if not summary_parts:

            summary_parts.append(

                "No significant soil findings were returned."

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

soil_agent = SoilAgent()