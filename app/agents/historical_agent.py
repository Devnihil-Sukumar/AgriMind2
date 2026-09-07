"""
==========================================================================
AgriMind

Historical Specialist Agent

Module 13Q

Responsibilities
----------------
1. Analyze historical farm records.
2. Compare current conditions with previous seasons.
3. Identify recurring patterns.
4. Learn from past successes and failures.
5. Generate a deterministic specialist summary.

Author : AgriMind Team
==========================================================================
"""

import json

from app.agents.base_agent import BaseAgent
from app.utils.json_extract import extract_json_object
from app.utils.context_summary import summarize_farm_context
from app.prompts.historical_prompt import HISTORICAL_PROMPT


class HistoricalAgent(BaseAgent):

    """
    Historical Specialist Agent
    """

    name = "HistoricalAgent"
    component = "historical"

    # This agent's prompt (crop profile + current-context summary +
    # full historical record set) runs close to qwen3:4b's 4096-token
    # context window even after trimming the redundant full-context
    # dump (see build_prompt below); on this machine it still timed out
    # at the full 300s Ollama budget. Routes to Groq directly instead
    # of relying on the Ollama-timeout-then-Groq-fallback path.
    provider = "groq"

    prompt = HISTORICAL_PROMPT

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context

    ):

        crop_profile = context["crop_profile"]

        historical = context["historical"]

        prompt = f"""
{HISTORICAL_PROMPT}

============================================================

CROP PROFILE

{json.dumps(
    crop_profile,
    indent=4,
    default=str
)}

============================================================

CURRENT FARM CONTEXT

{json.dumps(
    summarize_farm_context(context),
    indent=4,
    default=str
)}

============================================================

HISTORICAL DATA

{json.dumps(
    historical,
    indent=4,
    default=str
)}

============================================================

TASK

Compare the CURRENT FARM CONDITIONS against the HISTORICAL RECORDS.

Determine

1. Similar historical seasons.
2. Successful farming practices.
3. Failed farming practices.
4. Recurring farming patterns.
5. Historical risks.
6. Historical opportunities.
7. Recommendation based on historical evidence.

If there are no historical records,
explicitly mention that no historical evidence is available.

Return ONLY valid JSON.

Schema

{{
    "analysis": "",
    "patterns": [],
    "previous_successes": [],
    "previous_failures": [],
    "recommendation": "",
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

            error_label="HistoricalAgent"

        )

        analysis = str(

            result.get(

                "analysis",

                ""

            )

        ).strip()

        patterns = result.get(

            "patterns",

            []

        )

        successes = result.get(

            "previous_successes",

            []

        )

        failures = result.get(

            "previous_failures",

            []

        )

        recommendation = str(

            result.get(

                "recommendation",

                ""

            )

        ).strip()

        confidence = float(

            result.get(

                "confidence",

                0

            )

        )

        ################################################################
        # Determine Historical Availability
        ################################################################

        historical_available = bool(

            patterns

            or

            successes

            or

            failures

        )

        summary_parts = []

        if analysis:

            summary_parts.append(

                analysis

            )

        if not historical_available:

            summary_parts.append(

                "No comparable historical records are available."

            )

        else:

            if patterns:

                summary_parts.append(

                    f"{len(patterns)} historical pattern(s) identified."

                )

            if successes:

                summary_parts.append(

                    f"{len(successes)} previous success(es) identified."

                )

            if failures:

                summary_parts.append(

                    f"{len(failures)} previous failure(s) identified."

                )

        if recommendation:

            summary_parts.append(

                f"Historical recommendation: {recommendation}"

            )

        if not summary_parts:

            summary_parts.append(

                "No significant historical findings were returned."

            )

        summary = " ".join(

            summary_parts

        )

        result["agent"] = self.name

        result["status"] = "completed"

        result["summary"] = summary

        result["analysis"] = analysis

        result["risks"] = result.get(

            "risks",

            []

        )

        result["opportunities"] = result.get(

            "opportunities",

            []

        )

        result["confidence"] = confidence

        result["metadata"] = {

            "historical_available":

                historical_available,

            "pattern_count":

                len(patterns),

            "success_count":

                len(successes),

            "failure_count":

                len(failures)

        }

        return result


##########################################################################

historical_agent = HistoricalAgent()