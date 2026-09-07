"""
==========================================================================
AgriMind

Decision Trace Builder

Module 13V — Rich Decision Trace

Responsibilities
----------------
1. Build a chronological decision trace.
2. Capture specialist findings.
3. Capture evidence ranking.
4. Capture collaborative reasoning.
5. Capture conflicts and consensus.
6. Capture executive decision.
7. Capture final recommendation.
8. Explain how evidence influenced the decision.
9. Produce a human-readable causal chain.

Author : AgriMind Team
==========================================================================
"""

from app.explainability.evidence_aggregator import (
    evidence_aggregator
)


class DecisionTraceBuilder:

    """
    Builds a complete causal decision trace.
    """

    ####################################################################
    # Helper
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
    # Specialist Trace
    ####################################################################

    def _specialist_trace(

        self,

        specialists,

        evidence

    ):

        trace = []

        ranked_evidence = evidence.get(

            "ranked_evidence",

            []

        )

        ############################################################
        # Group ranked evidence by source
        ############################################################

        source_findings = {}

        for item in ranked_evidence:

            source = item.get(

                "source",

                "Unknown"

            )

            source_findings.setdefault(

                source,

                []

            ).append(

                item

            )

        ############################################################

        for step_number, (

            agent_name,

            output

        ) in enumerate(

            specialists.items(),

            start=1

        ):

            summary = self._text(

                output.get(

                    "summary"

                ),

                output.get(

                    "analysis",

                    "No specialist analysis available."

                )

            )

            confidence = float(

                output.get(

                    "confidence",

                    0

                )

            )

            findings = source_findings.get(

                agent_name,

                []

            )

            risks = output.get(

                "risks",

                []

            )

            opportunities = output.get(

                "opportunities",

                []

            )

            trace.append(

                {

                    "step":

                        step_number,

                    "stage":

                        "Specialist",

                    "source":

                        agent_name,

                    "finding":

                        summary,

                    "confidence":

                        round(

                            confidence,

                            4

                        ),

                    "key_risks":

                        risks,

                    "key_opportunities":

                        opportunities,

                    "ranked_evidence":

                        findings[:3],

                    "influence":

                        (

                            "Contributed evidence to the collaborative "

                            "reasoning stage."

                        )

                }

            )

        return trace

    ####################################################################
    # Evidence Trace
    ####################################################################

    def _evidence_trace(

        self,

        evidence,

        start_step

    ):

        trace = []

        ranked = evidence.get(

            "ranked_evidence",

            []

        )

        ############################################################
        # Only expose the strongest evidence
        ############################################################

        for index, item in enumerate(

            ranked[:5],

            start=start_step

        ):

            trace.append(

                {

                    "step":

                        index,

                    "stage":

                        "Evidence Ranking",

                    "source":

                        item.get(

                            "source",

                            "Unknown"

                        ),

                    "finding":

                        item.get(

                            "finding",

                            ""

                        ),

                    "confidence":

                        item.get(

                            "confidence",

                            0

                        ),

                    "reliability":

                        item.get(

                            "reliability",

                            0

                        ),

                    "decision_relevance":

                        item.get(

                            "decision_relevance",

                            0

                        ),

                    "evidence_score":

                        item.get(

                            "evidence_score",

                            0

                        ),

                    "importance":

                        item.get(

                            "importance",

                            "Unknown"

                        ),

                    "influence":

                        (

                            "Ranked according to confidence, source "

                            "reliability, evidence type, and relevance "

                            "to the final decision."

                        )

                }

            )

        return trace

    ####################################################################
    # Reasoning Trace
    ####################################################################

    def _reasoning_trace(

        self,

        reasoning,

        step

    ):

        summary = self._text(

            getattr(

                reasoning,

                "summary",

                ""

            ),

            "Collaborative reasoning combined the available specialist evidence."

        )

        consensus = self._text(

            getattr(

                reasoning,

                "consensus",

                ""

            ),

            "No explicit consensus statement was available."

        )

        risks = getattr(

            reasoning,

            "merged_risks",

            []

        )

        opportunities = getattr(

            reasoning,

            "merged_opportunities",

            []

        )

        conflicts = getattr(

            reasoning,

            "conflicts",

            []

        )

        confidence = float(

            getattr(

                reasoning,

                "confidence",

                0

            )

        )

        return {

            "step":

                step,

            "stage":

                "Collaborative Reasoning",

            "source":

                "CollaborativeEngine",

            "finding":

                summary,

            "confidence":

                round(

                    confidence,

                    4

                ),

            "consensus":

                consensus,

            "merged_risks":

                risks,

            "merged_opportunities":

                opportunities,

            "conflicts":

                conflicts,

            "influence":

                (

                    "Converted specialist evidence into a combined "

                    "decision context."

                )

        }

    ####################################################################
    # Executive Trace
    ####################################################################

    def _executive_trace(

        self,

        executive_decision,

        step

    ):

        decision = self._text(

            executive_decision.get(

                "decision",

                executive_decision.get(

                    "executive_decision",

                    ""

                )

            ),

            "No executive decision was available."

        )

        justification = self._text(

            executive_decision.get(

                "justification",

                ""

            ),

            "The executive decision was produced from collaborative reasoning."

        )

        confidence = float(

            executive_decision.get(

                "confidence",

                0

            )

        )

        priority = executive_decision.get(

            "priority"

        )

        return {

            "step":

                step,

            "stage":

                "Executive Decision",

            "source":

                "ExecutiveAgent",

            "finding":

                decision,

            "confidence":

                round(

                    confidence,

                    4

                ),

            "priority":

                priority,

            "justification":

                justification,

            "influence":

                (

                    "Converted the collaborative reasoning result into "

                    "an actionable executive decision."

                )

        }

    ####################################################################
    # Recommendation Trace
    ####################################################################

    def _recommendation_trace(

        self,

        recommendation,

        step

    ):

        recommendation_text = self._text(

            recommendation.get(

                "recommendation",

                ""

            ),

            recommendation.get(

                "executive_decision",

                ""

            )

        )

        justification = self._text(

            recommendation.get(

                "justification",

                ""

            )

        )

        actions = recommendation.get(

            "actions",

            []

        )

        confidence = float(

            recommendation.get(

                "confidence",

                0

            )

        )

        return {

            "step":

                step,

            "stage":

                "Recommendation",

            "source":

                "RecommendationAgent",

            "finding":

                recommendation_text,

            "confidence":

                round(

                    confidence,

                    4

                ),

            "actions":

                actions,

            "justification":

                justification,

            "influence":

                (

                    "Translated the executive decision into concrete "

                    "recommended actions."

                )

        }

    ####################################################################
    # Causal Chain
    ####################################################################

    def _build_causal_chain(

        self,

        specialists,

        evidence,

        reasoning,

        executive_decision,

        recommendation

    ):

        chain = []

        ############################################################
        # Strongest evidence
        ############################################################

        ranked = evidence.get(

            "ranked_evidence",

            []

        )

        for item in ranked[:3]:

            chain.append(

                {

                    "from":

                        item.get(

                            "source",

                            "Unknown"

                        ),

                    "to":

                        "CollaborativeReasoning",

                    "relationship":

                        "supports",

                    "evidence":

                        item.get(

                            "finding",

                            ""

                        ),

                    "strength":

                        item.get(

                            "evidence_score",

                            0

                        )

                }

            )

        ############################################################
        # Reasoning → Executive
        ############################################################

        reasoning_summary = self._text(

            getattr(

                reasoning,

                "summary",

                ""

            )

        )

        decision = self._text(

            executive_decision.get(

                "decision",

                executive_decision.get(

                    "executive_decision",

                    ""

                )

            )

        )

        chain.append(

            {

                "from":

                    "CollaborativeReasoning",

                "to":

                    "ExecutiveAgent",

                "relationship":

                    "informs",

                "evidence":

                    reasoning_summary,

                "strength":

                    float(

                        getattr(

                            reasoning,

                            "confidence",

                            0

                        )

                    )

            }

        )

        ############################################################
        # Executive → Recommendation
        ############################################################

        recommendation_text = self._text(

            recommendation.get(

                "recommendation",

                ""

            )

        )

        chain.append(

            {

                "from":

                    "ExecutiveAgent",

                "to":

                    "RecommendationAgent",

                "relationship":

                    "produces",

                "evidence":

                    decision,

                "strength":

                    float(

                        executive_decision.get(

                            "confidence",

                            0

                        )

                    )

            }

        )

        ############################################################
        # Recommendation output
        ############################################################

        chain.append(

            {

                "from":

                    "RecommendationAgent",

                "to":

                    "Farmer",

                "relationship":

                    "recommends",

                "evidence":

                    recommendation_text,

                "strength":

                    float(

                        recommendation.get(

                            "confidence",

                            0

                        )

                    )

            }

        )

        return chain

    ####################################################################
    # Build
    ####################################################################

    def build(

        self,

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
        # Specialist stage
        ############################################################

        specialist_trace = self._specialist_trace(

            specialists,

            evidence

        )

        ############################################################
        # Evidence stage
        ############################################################

        evidence_trace = self._evidence_trace(

            evidence,

            len(

                specialist_trace

            ) + 1

        )

        ############################################################
        # Reasoning
        ############################################################

        reasoning_step = (

            len(

                specialist_trace

            )

            +

            len(

                evidence_trace

            )

            +

            1

        )

        reasoning_trace = self._reasoning_trace(

            reasoning,

            reasoning_step

        )

        ############################################################
        # Executive
        ############################################################

        executive_step = reasoning_step + 1

        executive_trace = self._executive_trace(

            executive_decision,

            executive_step

        )

        ############################################################
        # Recommendation
        ############################################################

        recommendation_step = executive_step + 1

        recommendation_trace = self._recommendation_trace(

            recommendation,

            recommendation_step

        )

        ############################################################
        # Complete chronological trace
        ############################################################

        trace = (

            specialist_trace

            +

            evidence_trace

            +

            [

                reasoning_trace,

                executive_trace,

                recommendation_trace

            ]

        )

        ############################################################
        # Causal chain
        ############################################################

        causal_chain = self._build_causal_chain(

            specialists,

            evidence,

            reasoning,

            executive_decision,

            recommendation

        )

        ############################################################
        # Summary
        ############################################################

        decision = self._text(

            executive_decision.get(

                "decision",

                executive_decision.get(

                    "executive_decision",

                    ""

                )

            )

        )

        trace_summary = (

            f"{len(specialists)} specialist agents produced evidence. "

            f"The strongest evidence was ranked before collaborative "

            f"reasoning converted the findings into the executive decision "

            f"'{decision}'. The RecommendationAgent then translated that "

            "decision into actionable guidance."

        )

        return {

            "steps":

                trace,

            "causal_chain":

                causal_chain,

            "summary":

                trace_summary,

            "total_steps":

                len(

                    trace

                ),

            "specialist_steps":

                len(

                    specialist_trace

                ),

            "evidence_steps":

                len(

                    evidence_trace

                ),

            "decision_step":

                executive_step,

            "recommendation_step":

                recommendation_step,

            "top_evidence":

                evidence.get(

                    "top_evidence",

                    []

                )

        }


##########################################################################

decision_trace_builder = DecisionTraceBuilder()