"""
==========================================================================
AgriMind

Explanation Engine

Module 5G

13R — Better Explanation Generation
13S — Runtime-Aware Limitations
13T — Context-Aware Alternatives
13U — Evidence Ranking
13V — Rich Decision Trace
13W — Farmer-Friendly Explanation

Responsibilities
----------------
1. Aggregate evidence.
2. Explain confidence.
3. Generate context-aware alternatives.
4. Build rich decision trace.
5. Generate runtime-aware limitations.
6. Generate monitoring plan.
7. Build evidence-grounded Qwen prompt.
8. Parse explanation response.
9. Guarantee meaningful explanation fields.
10. Generate farmer-friendly explanation.
11. Return the Explanation object.

Author : AgriMind Team
==========================================================================
"""

import json

from app.models.explanation import Explanation

from app.explainability.evidence_aggregator import (
    evidence_aggregator
)

from app.explainability.confidence_explainer import (
    confidence_explainer
)

from app.explainability.alternative_generator import (
    alternative_generator
)

from app.explainability.decision_trace_builder import (
    decision_trace_builder
)

from app.explainability.limitation_generator import (
    limitation_generator
)

from app.explainability.monitoring_generator import (
    monitoring_generator
)

from app.prompts.explanation_prompt import (
    EXPLANATION_PROMPT
)

from app.utils.llm_client import (
    llm_client
)

from app.utils.context_summary import (
    summarize_crop_profile,
    summarize_farm_context,
    unavailable_sources
)

from app.utils.prompt_budget import (
    compact_json,
    truncate_text
)

from app.utils.provider_config import (
    get_max_prompt_tokens
)

from app.utils.json_extract import (
    extract_json_substring
)


class ExplanationEngine:

    """
    Explainable Recommendation Engine
    """

    ####################################################################
    # JSON Serialization Helper
    ####################################################################

    def _json(

        self,

        value

    ):

        return json.dumps(

            value,

            indent=4,

            default=str

        )

    ####################################################################
    # Safe Text
    ####################################################################

    def _text(

        self,

        value,

        fallback=""

    ):

        if value is None:

            return fallback

        return str(

            value

        ).strip() or fallback

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(

        self,

        context,

        specialists,

        reasoning,

        executive_decision,

        recommendation

    ):

        ############################################################
        # Evidence
        ############################################################

        evidence = evidence_aggregator.aggregate(

            specialists,

            reasoning,

            executive_decision

        )

        ############################################################
        # Confidence
        ############################################################

        confidence = confidence_explainer.explain(

            specialists,

            reasoning,

            executive_decision

        )

        ############################################################
        # Alternatives
        ############################################################

        alternatives = alternative_generator.generate(

            executive_decision,

            reasoning,

            context

        )

        ############################################################
        # Decision Trace
        ############################################################

        decision_trace = decision_trace_builder.build(

            specialists,

            reasoning,

            executive_decision,

            recommendation

        )

        ############################################################
        # Limitations
        ############################################################

        limitations = limitation_generator.generate(

            specialists,

            reasoning,

            executive_decision,

            context

        )

        ############################################################
        # Monitoring
        ############################################################

        monitoring = monitoring_generator.generate(

            specialists,

            executive_decision,

            recommendation,

            context

        )

        ############################################################
        # Prompt
        ############################################################

        ############################################################
        # Prompt
        #
        # Only the narrative fields are model-generated. Evidence,
        # trace, alternatives, limitations and monitoring are attached
        # deterministically after generation, so they are summarized
        # here rather than dumped in full.
        ############################################################

        missing = unavailable_sources(
            context
        )

        specialist_digest = {

            name: {

                "status": output.get(
                    "status"
                ),

                "confidence": output.get(
                    "confidence"
                ),

                "analysis": truncate_text(
                    output.get(
                        "analysis",
                        ""
                    ),
                    340
                ),

                "risks": output.get(
                    "risks",
                    []
                )[:3],

                "opportunities": output.get(
                    "opportunities",
                    []
                )[:3]

            }

            for name, output in (
                specialists.items()
                if isinstance(specialists, dict)
                else []
            )
            if isinstance(output, dict)
        }

        prompt = f"""

{EXPLANATION_PROMPT}

======================================================================

FARM CONTEXT SUMMARY

{compact_json(
    summarize_farm_context(context),
    max_chars=1700
)}

======================================================================

CROP PROFILE

{compact_json(
    summarize_crop_profile(
        context.get(
            "crop_profile",
            {}
        )
    ),
    max_chars=750
)}

======================================================================

EVIDENCE SOURCES UNAVAILABLE THIS RUN

{compact_json(missing) if missing else "None. All sources returned data."}

======================================================================

EXECUTIVE DECISION

{compact_json(executive_decision, max_chars=1200)}

======================================================================

FINAL RECOMMENDATION

{compact_json(recommendation, max_chars=1000)}

======================================================================

SPECIALIST FINDINGS

{compact_json(specialist_digest, max_chars=1700)}

======================================================================

COLLABORATIVE REASONING

Summary:

{truncate_text(getattr(reasoning, "summary", ""), 700)}

Consensus:

{truncate_text(getattr(reasoning, "consensus", ""), 500)}

Merged Risks:

{compact_json(
    getattr(reasoning, "merged_risks", []),
    max_chars=600
)}

Merged Opportunities:

{compact_json(
    getattr(reasoning, "merged_opportunities", []),
    max_chars=600
)}

======================================================================

CONFIDENCE ANALYSIS

{compact_json(confidence, max_chars=550)}

======================================================================

TOP RANKED EVIDENCE

{compact_json(
    evidence,
    max_chars=950,
    max_list_items=4,
    max_string_chars=200
)}

======================================================================

REJECTED ALTERNATIVES

{compact_json(
    alternatives,
    max_chars=650,
    max_list_items=3,
    max_string_chars=190
)}

======================================================================

RUNTIME LIMITATIONS

{compact_json(
    limitations,
    max_chars=600,
    max_list_items=4,
    max_string_chars=180
)}

======================================================================

MONITORING PLAN

{compact_json(
    monitoring,
    max_chars=450,
    max_list_items=4,
    max_string_chars=170
)}

======================================================================

FARMER-FRIENDLY OUTPUT

Generate a separate farmer-friendly explanation.

Use simple language.

Explain:

1. What is happening.
2. What the farmer should do.
3. Why the action is recommended.
4. What should be monitored next.

Do not mention:

- AI agents
- LLMs
- models
- prompts
- JSON
- evidence scores
- confidence scores
- internal architecture

Do not invent measurements or observations.

Do not describe any evidence source listed as unavailable as if it
had produced a reading.

Maximum 4 sentences.

======================================================================

FINAL INSTRUCTIONS

Generate a complete explanation.

The following fields MUST contain meaningful content:

executive_summary
explanation
reasoning_summary
decision_trace_summary
confidence_explanation
farmer_message

Do not restate the structured artifacts above. They are attached to
the response separately. Write the narrative only.

Return ONLY valid JSON.

"""

        return prompt

    ####################################################################
    # Clean LLM Response
    ####################################################################

    def clean_response(

        self,

        response

    ):

        if response is None:

            raise ValueError(

                "Explanation Engine received empty LLM response."

            )

        response = str(

            response

        ).strip()

        ############################################################
        # Escape-aware extraction.
        #
        # openai/gpt-oss-120b is a reasoning model and can emit
        # commentary around the JSON body. A naive find("{")/
        # rfind("}") slice grabs the LAST brace in the WHOLE
        # response, which can belong to unrelated trailing text and
        # produce a slice that fails json.loads() with a confusing
        # "Expecting ',' delimiter" error far from the real problem.
        ############################################################

        return extract_json_substring(

            response,

            error_label="Explanation Engine"

        )

    ####################################################################
    # Farmer-Friendly Fallback
    ####################################################################

    def build_farmer_message(

        self,

        context,

        executive_decision,

        recommendation

    ):

        decision = self._text(

            executive_decision.get(

                "decision",

                executive_decision.get(

                    "executive_decision",

                    ""

                )

            ),

            "the recommended action"

        )

        recommendation_text = self._text(

            recommendation.get(

                "recommendation",

                ""

            ),

            decision

        )

        ############################################################
        # Weather
        ############################################################

        weather = context.get(

            "weather",

            {}

        )

        weather_data = weather.get(

            "raw_data",

            weather

        )

        weather_assessment = weather.get(

            "assessment",

            {}

        )

        rainfall = weather_data.get(

            "rainfall"

        )

        temperature = weather_data.get(

            "temperature"

        )

        weather_risks = weather_assessment.get(

            "identified_risks",

            weather_assessment.get(

                "risks",

                []

            )

        )

        ############################################################
        # Satellite
        ############################################################

        satellite = context.get(

            "satellite",

            {}

        )

        vegetation = satellite.get(

            "vegetation",

            {}

        )

        water = satellite.get(

            "water",

            {}

        )

        satellite_reasons = []

        health = vegetation.get(

            "health"

        )

        stress = water.get(

            "stress"

        )

        if health:

            satellite_reasons.append(

                f"crop health is {health.lower()}"

            )

        if stress:

            satellite_reasons.append(

                f"water stress is {stress.lower()}"

            )

        ############################################################
        # Soil
        ############################################################

        soil = context.get(

            "soil",

            {}

        )

        soil_assessment = soil.get(

            "assessment",

            {}

        )

        soil_risks = soil_assessment.get(

            "risks",

            []

        )

        ############################################################
        # Market
        ############################################################

        market = context.get(

            "market",

            {}

        )

        top_markets = market.get(

            "top_markets",

            []

        )

        ############################################################
        # Build human-friendly reason
        ############################################################

        reasons = []

        if weather_risks:

            reasons.append(

                "weather conditions require attention"

            )

        elif rainfall is not None:

            try:

                if float(rainfall) < 1:

                    reasons.append(

                        "recent rainfall is very low"

                    )

            except (

                TypeError,

                ValueError

            ):

                pass

        if satellite_reasons:

            reasons.append(

                "crop monitoring shows "

                + " and ".join(

                    satellite_reasons[:2]

                )

            )

        if soil_risks:

            reasons.append(

                "some soil conditions need attention"

            )

        if top_markets and (

            "sell" in recommendation_text.lower()

            or

            "market" in recommendation_text.lower()

        ):

            best_market = top_markets[0]

            reasons.append(

                "market conditions provide a selling opportunity"

            )

        if not reasons:

            reasons.append(

                "the available farm information supports this action"

            )

        reason_text = " and ".join(

            reasons[:2]

        )

        ############################################################
        # Monitoring
        ############################################################

        monitoring_parts = []

        if satellite_reasons:

            monitoring_parts.append(

                "watch crop health and water stress"

            )

        if soil_risks:

            monitoring_parts.append(

                "check soil condition"

            )

        if rainfall is not None:

            monitoring_parts.append(

                "monitor rainfall and soil moisture"

            )

        if not monitoring_parts:

            monitoring_parts.append(

                "monitor the crop over the next few days"

            )

        monitoring_text = ", ".join(

            monitoring_parts[:2]

        )

        ############################################################
        # Final message
        ############################################################

        return (

            f"AgriMind recommends {recommendation_text}. "

            f"This is because {reason_text}. "

            f"After taking the recommended action, "

            f"{monitoring_text}."

        )

    ####################################################################
    # Build Fallback Explanation
    ####################################################################

    def build_fallback_explanation(

        self,

        specialists,

        reasoning,

        executive_decision,

        recommendation,

        context

    ):

        ############################################################
        # Specialist summaries
        ############################################################

        summaries = []

        for agent_name, output in specialists.items():

            summary = self._text(

                output.get(

                    "summary"

                ),

                output.get(

                    "analysis",

                    ""

                )

            )

            if summary:

                summaries.append(

                    f"{agent_name}: {summary}"

                )

        ############################################################
        # Decision
        ############################################################

        decision = self._text(

            executive_decision.get(

                "executive_decision"

            ),

            executive_decision.get(

                "decision",

                "the current recommended action"

            )

        )

        rec_text = self._text(

            recommendation.get(

                "recommendation"

            ),

            decision

        )

        ############################################################
        # Reasoning
        ############################################################

        reasoning_summary = self._text(

            getattr(

                reasoning,

                "summary",

                ""

            ),

            "The specialist analyses were combined through collaborative reasoning."

        )

        ############################################################
        # Narrative
        ############################################################

        explanation_parts = []

        if summaries:

            explanation_parts.append(

                "The recommendation is supported by specialist evidence: "

                + " ".join(

                    summaries

                )

            )

        explanation_parts.append(

            "Collaborative reasoning concluded that "

            + reasoning_summary

        )

        explanation_parts.append(

            f"The final decision is '{decision}', leading to the "

            f"recommendation: {rec_text}"

        )

        explanation = " ".join(

            explanation_parts

        )

        ############################################################
        # Farmer message
        ############################################################

        farmer_message = self.build_farmer_message(

            context,

            executive_decision,

            recommendation

        )

        return {

            "executive_summary":

                f"{decision}. {rec_text}",

            "explanation":

                explanation,

            "reasoning_summary":

                reasoning_summary,

            "decision_trace_summary":

                "Specialist evidence was combined through collaborative "

                "reasoning, followed by an executive decision and final "

                "recommendation.",

            "confidence_explanation":

                "Confidence reflects the available specialist, reasoning, "

                "and executive evidence.",

            "farmer_message":

                farmer_message

        }

    ####################################################################
    # Explain
    ####################################################################

    def explain(

        self,

        context,

        specialists,

        reasoning,

        executive_decision,

        recommendation

    ):

        ############################################################
        # Build prompt
        ############################################################

        prompt = self.build_prompt(

            context,

            specialists,

            reasoning,

            executive_decision,

            recommendation

        )

        ############################################################
        # Deterministic components
        #
        # These are calculated before the LLM call so the fallback
        # explanation can use exactly the same upstream evidence.
        ############################################################

        evidence = evidence_aggregator.aggregate(

            specialists,

            reasoning,

            executive_decision

        )

        confidence = confidence_explainer.explain(

            specialists,

            reasoning,

            executive_decision

        )

        alternatives = alternative_generator.generate(

            executive_decision,

            reasoning,

            context

        )

        decision_trace = decision_trace_builder.build(

            specialists,

            reasoning,

            executive_decision,

            recommendation

        )

        limitations = limitation_generator.generate(

            specialists,

            reasoning,

            executive_decision,

            context

        )

        monitoring = monitoring_generator.generate(

            specialists,

            executive_decision,

            recommendation,

            context

        )

        ############################################################
        # LLM explanation
        #
        # Explanation is NON-CRITICAL. Any LLM/API/JSON failure
        # falls back to deterministic structured explanation.
        ############################################################

        try:

            raw = llm_client.generate(

                prompt=prompt,

                component="explanation",

                max_prompt_tokens=get_max_prompt_tokens(
                    "explanation"
                )

            )

            cleaned = self.clean_response(

                raw

            )

            result = json.loads(

                cleaned

            )

            if not isinstance(

                result,

                dict

            ):

                raise ValueError(

                    "Explanation Engine LLM response must be a JSON object."

                )

        except Exception as error:

            print()

            print(

                "⚠ Explanation Engine LLM failed: "

                f"{error}"

            )

            print(

                "Using deterministic structured fallback."

            )

            ########################################################
            # Build fallback
            ########################################################

            fallback = self.build_fallback_explanation(

                specialists,

                reasoning,

                executive_decision,

                recommendation,

                context

            )

            ########################################################
            # Attach deterministic explainability artifacts
            ########################################################

            fallback["evidence"] = evidence

            fallback["decision_trace"] = decision_trace

            fallback["limitations"] = limitations

            fallback["future_monitoring"] = monitoring

            fallback["risk_analysis"] = getattr(

                reasoning,

                "merged_risks",

                []

            )

            fallback["opportunity_analysis"] = getattr(

                reasoning,

                "merged_opportunities",

                []

            )

            fallback["rejected_alternatives"] = alternatives

            fallback["confidence_breakdown"] = confidence

            if isinstance(

                confidence,

                dict

            ):

                fallback_confidence = confidence.get(

                    "overall",

                    confidence.get(

                        "confidence",

                        0.0

                    )

                )

            else:

                fallback_confidence = 0.0

            fallback["confidence"] = fallback_confidence

            fallback["generation_mode"] = "deterministic_fallback"

            ########################################################
            # Guarantee required fields
            ########################################################

            fallback["executive_decision"] = self._text(

                fallback.get(

                    "executive_decision"

                ),

                executive_decision.get(

                    "executive_decision",

                    executive_decision.get(

                        "decision",

                        ""

                    )

                )

            )

            fallback["recommendation"] = self._text(

                fallback.get(

                    "recommendation"

                ),

                recommendation.get(

                    "recommendation",

                    ""

                )

            )

            fallback["executive_summary"] = self._text(

                fallback.get(

                    "executive_summary"

                ),

                (

                    f"{fallback['executive_decision']}. "

                    f"{fallback['recommendation']}"

                )

            )

            fallback["explanation"] = self._text(

                fallback.get(

                    "explanation"

                ),

                fallback["executive_summary"]

            )

            fallback["reasoning_summary"] = self._text(

                fallback.get(

                    "reasoning_summary"

                ),

                (

                    "Specialist evidence was combined through "

                    "collaborative reasoning."

                )

            )

            fallback["decision_trace_summary"] = self._text(

                fallback.get(

                    "decision_trace_summary"

                ),

                (

                    "Specialist evidence → collaborative reasoning "

                    "→ executive decision → recommendation."

                )

            )

            fallback["confidence_explanation"] = self._text(

                fallback.get(

                    "confidence_explanation"

                ),

                (

                    "The explanation was generated using deterministic "

                    "fallback because the explanation LLM was unavailable."

                )

            )

            fallback["farmer_message"] = self._text(

                fallback.get(

                    "farmer_message"

                ),

                self.build_farmer_message(

                    context,

                    executive_decision,

                    recommendation

                )

            )

            ########################################################
            # Return structured Explanation object
            ########################################################

            explanation = Explanation(

                executive_decision=fallback[
                    "executive_decision"
                ],

                executive_summary=fallback[
                    "executive_summary"
                ],

                recommendation=fallback[
                    "recommendation"
                ],

                explanation=fallback[
                    "explanation"
                ],

                reasoning_summary=fallback[
                    "reasoning_summary"
                ],

                decision_trace=fallback.get(

                    "decision_trace",

                    decision_trace

                ),

                evidence=fallback.get(

                    "evidence",

                    evidence

                ),

                risks=fallback.get(

                    "risk_analysis",

                    getattr(

                        reasoning,

                        "merged_risks",

                        []

                    )

                ),

                opportunities=fallback.get(

                    "opportunity_analysis",

                    getattr(

                        reasoning,

                        "merged_opportunities",

                        []

                    )

                ),

                rejected_alternatives=fallback.get(

                    "rejected_alternatives",

                    alternatives

                ),

                limitations=fallback.get(

                    "limitations",

                    limitations

                ),

                monitoring_plan=fallback.get(

                    "future_monitoring",

                    monitoring

                ),

                confidence_breakdown=fallback.get(

                    "confidence_breakdown",

                    confidence

                ),

                overall_confidence=fallback.get(

                    "confidence",

                    0

                )

            )

            ########################################################
            # Additional 13W fields
            ########################################################

            if hasattr(

                explanation,

                "__dict__"

            ):

                explanation.__dict__[

                    "decision_trace_summary"

                ] = fallback[

                    "decision_trace_summary"

                ]

                explanation.__dict__[

                    "confidence_explanation"

                ] = fallback[

                    "confidence_explanation"

                ]

                explanation.__dict__[

                    "farmer_message"

                ] = fallback[

                    "farmer_message"

                ]

                explanation.__dict__[

                    "generation_mode"

                ] = fallback[

                    "generation_mode"

                ]

            return explanation

        ############################################################
        # Successful LLM path
        ############################################################

        result["generation_mode"] = "llm"

        ############################################################
        # Final fields
        ############################################################

        fallback = self.build_fallback_explanation(

            specialists,

            reasoning,

            executive_decision,

            recommendation,

            context

        )

        executive_text = self._text(

            result.get(

                "executive_decision"

            ),

            executive_decision.get(

                "executive_decision",

                executive_decision.get(

                    "decision",

                    ""

                )

            )

        )

        summary_text = self._text(

            result.get(

                "executive_summary"

            ),

            fallback["executive_summary"]

        )

        recommendation_text = self._text(

            result.get(

                "recommendation"

            ),

            recommendation.get(

                "recommendation",

                ""

            )

        )

        explanation_text = self._text(

            result.get(

                "explanation"

            ),

            fallback["explanation"]

        )

        reasoning_text = self._text(

            result.get(

                "reasoning_summary"

            ),

            fallback["reasoning_summary"]

        )

        trace_summary = self._text(

            result.get(

                "decision_trace_summary"

            ),

            fallback["decision_trace_summary"]

        )

        confidence_text = self._text(

            result.get(

                "confidence_explanation"

            ),

            fallback["confidence_explanation"]

        )

        farmer_message = self._text(

            result.get(

                "farmer_message"

            ),

            fallback["farmer_message"]

        )

        ############################################################
        # Final Explanation object
        ############################################################

        explanation = Explanation(

            executive_decision=

                executive_text,

            executive_summary=

                summary_text,

            recommendation=

                recommendation_text,

            explanation=

                explanation_text,

            reasoning_summary=

                reasoning_text,

            decision_trace=

                result.get(

                    "decision_trace",

                    decision_trace

                ),

            evidence=

                result.get(

                    "evidence",

                    evidence

                ),

            risks=

                result.get(

                    "risk_analysis",

                    getattr(

                        reasoning,

                        "merged_risks",

                        []

                    )

                ),

            opportunities=

                result.get(

                    "opportunity_analysis",

                    getattr(

                        reasoning,

                        "merged_opportunities",

                        []

                    )

                ),

            rejected_alternatives=

                result.get(

                    "rejected_alternatives",

                    alternatives

                ),

            limitations=

                result.get(

                    "limitations",

                    limitations

                ),

            monitoring_plan=

                result.get(

                    "future_monitoring",

                    monitoring

                ),

            confidence_breakdown=

                confidence,

            overall_confidence=

                confidence.get(

                    "overall",

                    0

                ),

        )

        ############################################################
        # Additional 13W fields
        ############################################################

        if hasattr(

            explanation,

            "__dict__"

        ):

            explanation.__dict__[

                "decision_trace_summary"

            ] = trace_summary

            explanation.__dict__[

                "confidence_explanation"

            ] = confidence_text

            explanation.__dict__[

                "farmer_message"

            ] = farmer_message

            ########################################################
            # This is the successful LLM path. Labelling it as a
            # fallback made every explanation report itself as
            # deterministic, which would misstate how the narrative
            # was actually produced.
            ########################################################

            explanation.__dict__[

                "generation_mode"

            ] = result.get(

                "generation_mode",

                "llm"

            )

        return explanation


##########################################################################
# Singleton
##########################################################################

explanation_engine = ExplanationEngine()