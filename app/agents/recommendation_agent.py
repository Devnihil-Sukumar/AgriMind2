"""
==========================================================================
AgriMind

Recommendation Agent

Module 5F

Responsibilities
----------------
1. Consume Executive Decision.
2. Use Crop Profile.
3. Produce executable farm recommendations.
4. Generate action plan.
5. Estimate monitoring strategy.

Provider Routing
----------------
This agent routes through the central llm_client using the
"recommendation" component, so the provider, completion budget and
prompt budget are all governed by provider_config rather than by a
hard-coded Groq call.

Prompt Budget
-------------
The executive decision is already a synthesis of every specialist
analysis, so this agent receives a compact farm-context summary
instead of the full collector payloads. Dumping the complete context
alongside the full reasoning object previously produced a request
larger than the entire Groq per-minute allowance.

Author : AgriMind Team
==========================================================================
"""

import logging

from app.prompts.recommendation_prompt import RECOMMENDATION_PROMPT
from app.utils.context_summary import (
    summarize_crop_profile,
    summarize_farm_context,
    unavailable_sources
)
from app.utils.llm_client import llm_client
from app.utils.prompt_budget import compact_json, truncate_text
from app.utils.provider_config import get_max_prompt_tokens

logger = logging.getLogger(__name__)


##########################################################################
# Response Schema
##########################################################################

RECOMMENDATION_SCHEMA = {

    "type": "object",

    "properties": {

        "recommendation": {"type": "string"},

        "priority": {"type": "string"},

        "justification": {"type": "string"},

        "actions": {
            "type": "array",
            "items": {"type": "string"}
        },

        "expected_outcome": {"type": "string"},

        "monitoring_plan": {
            "type": "array",
            "items": {"type": "string"}
        },

        "confidence": {"type": "number"}

    },

    "required": [
        "recommendation",
        "priority",
        "justification",
        "actions",
        "confidence"
    ]
}


class RecommendationAgent:

    """
    Final Decision Agent
    """

    name = "RecommendationAgent"

    component = "recommendation"

    ####################################################################
    # Executive Decision Digest
    ####################################################################

    def summarize_executive(
        self,
        executive
    ):
        """
        Reduce the executive decision to the fields an execution plan
        is actually derived from.
        """

        if not isinstance(executive, dict):

            return {}

        digest = {

            "decision": executive.get(
                "decision",
                executive.get(
                    "executive_decision",
                    ""
                )
            ),

            "priority": executive.get("priority"),

            "urgency": executive.get("urgency"),

            "risk_level": executive.get("risk_level"),

            "action_order": executive.get("action_order"),

            "priorities": executive.get("priorities", []),

            "impact": executive.get("impact", {}),

            "confidence": executive.get("confidence")

        }

        ################################################################
        # Keep only the justification from the summary block
        ################################################################

        summary = executive.get("summary")

        if isinstance(summary, dict):

            digest["justification"] = truncate_text(
                summary.get(
                    "justification",
                    summary.get(
                        "executive",
                        ""
                    )
                ),
                600
            )

        return {
            key: value
            for key, value in digest.items()
            if value not in (None, "", [], {})
        }

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(
        self,
        context,
        reasoning,
        executive
    ):

        crop_profile = summarize_crop_profile(
            context.get(
                "crop_profile",
                {}
            )
        )

        farm_summary = summarize_farm_context(
            context
        )

        missing = unavailable_sources(
            context
        )

        ################################################################

        prompt = f"""
{RECOMMENDATION_PROMPT}

================================================================

CROP PROFILE

{compact_json(crop_profile, max_chars=1800)}

================================================================

FARM CONTEXT SUMMARY

{compact_json(farm_summary, max_chars=3000)}

================================================================

EVIDENCE SOURCES UNAVAILABLE THIS RUN

{compact_json(missing) if missing else "None. All sources returned data."}

================================================================

COLLABORATIVE REASONING

Summary

{truncate_text(getattr(reasoning, "summary", ""), 1200)}

------------------------------------------------------------

Consensus

{truncate_text(getattr(reasoning, "consensus", ""), 800)}

------------------------------------------------------------

Merged Risks

{compact_json(getattr(reasoning, "merged_risks", []), max_chars=1200)}

------------------------------------------------------------

Merged Opportunities

{compact_json(getattr(reasoning, "merged_opportunities", []), max_chars=1200)}

------------------------------------------------------------

Reasoning Confidence

{getattr(reasoning, "confidence", 0)}

================================================================

EXECUTIVE DECISION

{compact_json(self.summarize_executive(executive), max_chars=2200)}

================================================================

TASK

The Executive Decision above is the validated farm decision.

Your responsibility is NOT to re-decide.

Your responsibility is to convert that executive decision into an
actionable farm execution plan.

Do not base any action on an evidence source listed as unavailable.

Return ONLY valid JSON.

Schema

{{
    "recommendation":"",
    "priority":"",
    "justification":"",
    "actions":[],
    "expected_outcome":"",
    "monitoring_plan":[],
    "confidence":0.95
}}

"""

        return prompt

    ####################################################################
    # Deterministic Fallback
    ####################################################################

    def build_fallback(
        self,
        context,
        reasoning,
        executive,
        error
    ):
        """
        Deterministic execution plan used when the recommendation LLM
        is unavailable.

        A recommendation failure previously left the Explanation Engine
        and the governance layer with nothing to reason about. The
        executive decision is already validated, so it can be restated
        as an execution plan without a model call.
        """

        executive_decision = ""

        priority = "Medium"

        if isinstance(executive, dict):

            executive_decision = str(
                executive.get(
                    "decision",
                    executive.get(
                        "executive_decision",
                        ""
                    )
                )
            ).strip()

            priority = str(
                executive.get(
                    "priority",
                    "Medium"
                )
            ).strip() or "Medium"

        if not executive_decision:

            executive_decision = truncate_text(
                getattr(
                    reasoning,
                    "consensus",
                    ""
                ),
                400
            )

        ################################################################
        # Actions derived from executive priorities
        ################################################################

        actions = []

        priorities = (
            executive.get("priorities", [])
            if isinstance(executive, dict)
            else []
        )

        if isinstance(priorities, list):

            for item in priorities[:5]:

                if isinstance(item, dict):

                    action = str(
                        item.get(
                            "action",
                            item.get(
                                "issue",
                                ""
                            )
                        )
                    ).strip()

                elif item:

                    action = str(item).strip()

                else:

                    action = ""

                if action:

                    actions.append(action)

        if not actions:

            actions = [
                str(risk).strip()
                for risk in list(
                    getattr(
                        reasoning,
                        "merged_risks",
                        []
                    )
                )[:3]
                if str(risk).strip()
            ]

        if not actions:

            actions = [
                "Review the executive decision with a local "
                "agricultural officer before acting."
            ]

        ################################################################
        # Monitoring derived from unavailable sources
        ################################################################

        monitoring = [
            f"Re-check {source} data before executing this plan."
            for source in unavailable_sources(context)
        ]

        monitoring.append(
            "Re-run the recommendation once the advisory model "
            "is reachable."
        )

        ################################################################

        return {

            "recommendation": executive_decision or (
                "No recommendation could be generated."
            ),

            "priority": priority,

            "justification": (
                "Generated deterministically from the validated "
                "executive decision because the recommendation model "
                f"was unavailable: {truncate_text(error, 200)}"
            ),

            "actions": actions,

            "expected_outcome": (
                "Outcome not modelled. This plan restates the "
                "executive decision without model-generated analysis."
            ),

            "monitoring_plan": monitoring,

            ############################################################
            # Confidence is deliberately reduced.
            #
            # A deterministic restatement carries less support than a
            # reasoned plan, and the governance layer must be able to
            # see that difference.
            ############################################################

            "confidence": 0.35,

            "generation_mode": "deterministic_fallback"

        }

    ####################################################################
    # Execute
    ####################################################################

    def execute(
        self,
        context,
        reasoning,
        executive
    ):

        prompt = self.build_prompt(
            context,
            reasoning,
            executive
        )

        ################################################################
        # LLM
        ################################################################

        try:

            result = llm_client.generate_json(

                prompt=prompt,

                schema=RECOMMENDATION_SCHEMA,

                component=self.component,

                max_prompt_tokens=get_max_prompt_tokens(
                    self.component
                )

            )

            result["generation_mode"] = "llm"

        except Exception as error:

            logger.warning(
                "RecommendationAgent LLM failed, using deterministic "
                "fallback: %s",
                error
            )

            print()

            print(
                f"⚠ RecommendationAgent LLM failed: {error}"
            )

            print(
                "Using deterministic executive-derived fallback."
            )

            result = self.build_fallback(
                context,
                reasoning,
                executive,
                str(error)
            )

        ################################################################
        # Normalize
        ################################################################

        result = self.normalize(
            result
        )

        ################################################################
        # Metadata
        ################################################################

        result["agent"] = self.name

        result["status"] = "completed"

        result["executive_decision"] = (
            executive.get(
                "decision",
                ""
            )
            if isinstance(executive, dict)
            else ""
        )

        result["executive_priority"] = (
            executive.get(
                "priority",
                ""
            )
            if isinstance(executive, dict)
            else ""
        )

        ################################################################

        return result

    ####################################################################
    # Normalize
    ####################################################################

    @staticmethod
    def normalize(
        result
    ):
        """
        Guarantee the fields downstream components read.

        The Explanation Engine and the governance layer both index into
        this structure, so missing or mistyped fields must not escape.
        """

        if not isinstance(result, dict):

            result = {
                "recommendation": str(result)
            }

        ################################################################
        # Some models emit "recommended_actions" per the prompt header
        ################################################################

        if not result.get("actions") and result.get(
            "recommended_actions"
        ):

            result["actions"] = result["recommended_actions"]

        for key in (
            "recommendation",
            "priority",
            "justification",
            "expected_outcome"
        ):

            result[key] = str(
                result.get(
                    key,
                    ""
                )
                or ""
            ).strip()

        for key in (
            "actions",
            "monitoring_plan"
        ):

            value = result.get(
                key,
                []
            )

            if isinstance(value, str):

                value = [value] if value.strip() else []

            elif not isinstance(value, list):

                value = [str(value)]

            result[key] = [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        try:

            confidence = float(
                result.get(
                    "confidence",
                    0.0
                )
            )

        except (TypeError, ValueError):

            confidence = 0.0

        result["confidence"] = max(
            0.0,
            min(
                confidence,
                1.0
            )
        )

        return result


##########################################################################

recommendation_agent = RecommendationAgent()
