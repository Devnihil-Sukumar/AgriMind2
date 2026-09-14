"""
==========================================================================
AgriMind

Satellite Specialist Agent

Module 13Q

Responsibilities
----------------
1. Analyze vegetation health.
2. Analyze water stress.
3. Analyze exposed soil.
4. Compare satellite indices with crop profile.
5. Generate a deterministic specialist summary.

Author : AgriMind Team
==========================================================================
"""

import json
from dataclasses import asdict

from app.agents.base_agent import BaseAgent
from app.models.specialist_output import SpecialistOutput
from app.prompts.satellite_prompt import SATELLITE_PROMPT
from app.utils.json_extract import extract_json_object


class SatelliteAgent(BaseAgent):

    """
    Satellite Specialist Agent
    """

    name = "SatelliteAgent"
    component = "satellite"

    # qwen3:4b via Ollama consistently echoed the schema's empty
    # placeholder values back verbatim instead of analyzing the NDVI/
    # NDWI/SAVI indices -- 2/2 retries failed the same way across every
    # observed run (~160s each, ~320s wasted per pipeline run for zero
    # usable output). Groq (already proven reliable for MarketAgent)
    # doesn't reproduce this failure mode.
    #
    # KNOWN LIMITATION on an Ollama-only deployment with no Groq key
    # (e.g. this machine as of Sept 2026): this agent fails fast with a
    # missing-API-key error on every request instead of running at all.
    # Removing this override is NOT a fix -- it reproduces the empty-
    # echo failure above, which is slower AND still produces nothing
    # usable. A real fix needs either a restored Groq key, or a
    # different/larger local model just for this agent.
    provider = "groq"

    ####################################################################
    # Availability
    ####################################################################

    @staticmethod
    def is_available(
        satellite
    ):
        """
        True only when the satellite collector returned usable imagery.
        """

        if not isinstance(satellite, dict):

            return False

        status = str(
            satellite.get(
                "status",
                ""
            )
        ).strip().lower()

        return status == "success"

    ####################################################################
    # Unavailable Output
    ####################################################################

    def unavailable_output(
        self,
        satellite
    ):
        """
        Deterministic specialist output for a satellite outage.

        Confidence is 0 and the analysis states the outage explicitly,
        so that collaborative reasoning, evidence ranking, runtime
        limitations and Bayesian governance all see a missing source
        rather than a confident empty one.
        """

        reason = ""

        if isinstance(satellite, dict):

            reason = str(
                satellite.get(
                    "error",
                    ""
                )
            ).strip()

        detail = f" Reason: {reason}" if reason else ""

        analysis = (
            "Satellite evidence is unavailable for this run. "
            "No Sentinel-2 vegetation or water indices could be "
            f"retrieved for this location.{detail} "
            "No vegetation health, water stress or soil exposure "
            "assessment was produced."
        )

        output = SpecialistOutput(

            agent=self.name,

            status="unavailable",

            analysis=analysis,

            summary=(
                "Satellite evidence was unavailable for this run, so no "
                "vegetation health, water stress or soil exposure "
                "assessment contributed to this decision."
            ),

            risks=[
                "Vegetation health and water stress could not be "
                "verified from satellite imagery."
            ],

            opportunities=[],

            confidence=0.0,

            metadata={

                "source_status": (
                    satellite.get(
                        "status",
                        "unavailable"
                    )
                    if isinstance(satellite, dict)
                    else "unavailable"
                ),

                "source_error": reason,

                "generation_mode": "deterministic_unavailable"

            }

        )

        return asdict(
            output
        )

    ####################################################################
    # Execute
    ####################################################################

    def execute(
        self,
        context
    ):
        """
        Skip the LLM entirely when there is no imagery to analyze.
        """

        satellite = context.get(
            "satellite",
            {}
        )

        if not self.is_available(
            satellite
        ):

            print(
                f"→ {self.name} skipped: satellite data unavailable"
            )

            return self.unavailable_output(
                satellite
            )

        return super().execute(
            context
        )

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context

    ):

        crop_profile = context["crop_profile"]

        satellite = context["satellite"]

        prompt = f"""
{SATELLITE_PROMPT}

============================================================

CROP PROFILE

{json.dumps(
    crop_profile,
    indent=4,
    default=str
)}

============================================================

CURRENT SATELLITE DATA

{json.dumps(
    satellite,
    indent=4,
    default=str
)}

============================================================

TASK

Compare the CURRENT SATELLITE INDICES against the CROP PROFILE.

Use the crop profile vegetation thresholds instead of generic
thresholds.

Evaluate

1. NDVI health.
2. NDWI water stress.
3. SAVI soil exposure.
4. Vegetation condition.
5. Water availability.
6. Irrigation need.
7. Satellite-related risks.
8. Satellite-related opportunities.
9. Overall vegetation assessment.

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

            error_label="SatelliteAgent"

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

                f"{len(risks)} satellite risk(s) identified."

            )

        if opportunities:

            summary_parts.append(

                f"{len(opportunities)} satellite opportunity(s) identified."

            )

        if not summary_parts:

            summary_parts.append(

                "No significant satellite findings were returned."

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

satellite_agent = SatelliteAgent()