import json

from dataclasses import asdict

from app.models.reasoning_models import EvidenceNode

from app.reasoning.evidence_graph import EvidenceGraph

from app.reasoning.conflict_detector import conflict_detector

from app.reasoning.consensus import consensus_builder

from app.reasoning.confidence_fusion import confidence_fusion

from app.reasoning.reasoning_output import CollaborativeReasoning

from app.prompts.collaborative_prompt import (
    SYSTEM_PROMPT,
    build_prompt
)

from app.utils.llm_client import llm_client


class CollaborativeEngine:
    """
    Multi-Agent Collaborative Reasoning Engine.

    Workflow
    --------
    Specialist Outputs
            ↓
       Evidence Graph
            ↓
      Conflict Detection
            ↓
         Consensus
            ↓
      Confidence Fusion
            ↓
       Gemini Synthesis
            ↓
    CollaborativeReasoning
    """

    ###########################################################
    # Build Evidence Graph
    ###########################################################

    def build_graph(
        self,
        specialist_outputs
    ):

        graph = EvidenceGraph()

        for output in specialist_outputs.values():

            node = EvidenceNode(

                agent=output["agent"],

                analysis=output["analysis"],

                risks=output.get(
                    "risks",
                    []
                ),

                opportunities=output.get(
                    "opportunities",
                    []
                ),

                confidence=output.get(
                    "confidence",
                    0.5
                ),

                metadata=output.get(
                    "metadata",
                    {}
                )

            )

            graph.add(node)

        return graph

    ###########################################################
    # Gemini Response Schema
    ###########################################################

    def get_response_schema(self):

        return {

            "type": "object",

            "properties": {

                "summary": {
                    "type": "string"
                },

                "consensus": {
                    "type": "string"
                },

                "merged_risks": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },

                "merged_opportunities": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },

                "conflicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string"
                            },
                            "severity": {
                                "type": "string"
                            },
                            "resolution": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "description",
                            "severity",
                            "resolution"
                        ]
                    }
                },

                "confidence": {
                    "type": "number"
                }

            },

            "required": [
                "summary",
                "consensus",
                "merged_risks",
                "merged_opportunities",
                "conflicts",
                "confidence"
            ]
        }

    ###########################################################
    # Safe Fallback
    ###########################################################

    def build_fallback(
        self,
        consensus,
        conflicts,
        confidence
    ):

        return {

            "summary":
                consensus.get(
                    "summary",
                    "Collaborative reasoning completed."
                ),

            "consensus":
                "Deterministic consensus generated "
                "because LLM-backed reasoning was unavailable.",

            "merged_risks":
                consensus.get(
                    "merged_risks",
                    []
                ),

            "merged_opportunities":
                consensus.get(
                    "merged_opportunities",
                    []
                ),

            "conflicts":
                conflicts
                if isinstance(
                    conflicts,
                    list
                )
                else [],

            "confidence":
                confidence

        }

    ###########################################################
    # Main Collaborative Reasoning
    ###########################################################

    def collaborative_reasoning(
        self,
        context,
        specialist_outputs
    ):

        #######################################################
        # Step 1 — Evidence Graph
        #######################################################

        graph = self.build_graph(
            specialist_outputs
        )

        #######################################################
        # Step 2 — Conflict Detection
        #######################################################

        conflicts = conflict_detector.detect(
            graph
        )

        #######################################################
        # Step 3 — Consensus
        #######################################################

        consensus = consensus_builder.build(
            graph
        )

        #######################################################
        # Step 4 — Confidence Fusion
        #######################################################

        confidence = confidence_fusion.compute(
            graph
        )

        #######################################################
        # Step 5 — Build Compact Gemini Prompt
        #######################################################

        prompt = build_prompt(

            context=context,

            evidence=graph.to_dict()

        )

        #######################################################
        # Step 6 — Gemini Structured Reasoning
        #######################################################

        try:

            reasoning = llm_client.generate_json(

                system_prompt=SYSTEM_PROMPT,

                prompt=prompt,

                schema=self.get_response_schema(),

                component="collaborative",

                temperature=0.2

            )

            print()
            print(
                "✓ Collaborative reasoning"
            )

        except Exception as error:

            print()
            print(
                "⚠ Collaborative reasoning failed:"
            )

            print(
                error
            )

            print(
                "Using deterministic collaborative fallback."
            )

            reasoning = self.build_fallback(

                consensus=consensus,

                conflicts=conflicts,

                confidence=confidence

            )

        #######################################################
        # Step 7 — Defensive normalization
        #######################################################

        summary = reasoning.get(
            "summary",
            consensus.get(
                "summary",
                ""
            )
        )

        consensus_text = reasoning.get(
            "consensus",
            ""
        )

        merged_risks = reasoning.get(
            "merged_risks",
            consensus.get(
                "merged_risks",
                []
            )
        )

        merged_opportunities = reasoning.get(
            "merged_opportunities",
            consensus.get(
                "merged_opportunities",
                []
            )
        )

        reasoning_conflicts = reasoning.get(
            "conflicts",
            conflicts
        )

        reasoning_confidence = reasoning.get(
            "confidence",
            confidence
        )

        #######################################################
        # Normalize confidence
        #######################################################

        try:

            reasoning_confidence = float(
                reasoning_confidence
            )

        except (
            TypeError,
            ValueError
        ):

            reasoning_confidence = float(
                confidence
            )

        if reasoning_confidence > 1:

            reasoning_confidence /= 100.0

        reasoning_confidence = max(
            0.0,
            min(
                reasoning_confidence,
                1.0
            )
        )

        #######################################################
        # Normalize lists
        #######################################################

        if not isinstance(
            merged_risks,
            list
        ):

            merged_risks = [
                str(
                    merged_risks
                )
            ]

        if not isinstance(
            merged_opportunities,
            list
        ):

            merged_opportunities = [
                str(
                    merged_opportunities
                )
            ]

        if not isinstance(
            reasoning_conflicts,
            list
        ):

            reasoning_conflicts = conflicts

        #######################################################
        # Step 8 — Return Standardized Object
        #######################################################

        return CollaborativeReasoning(

            summary=str(
                summary
            ),

            consensus=str(
                consensus_text
            ),

            merged_risks=merged_risks,

            merged_opportunities=
                merged_opportunities,

            conflicts=reasoning_conflicts,

            confidence=
                reasoning_confidence,

            evidence=
                graph.to_dict(),

            metadata={

                "agents":
                    graph.get_agents(),

                "agent_count":
                    len(graph.nodes),

                "llm_provider":
                    "gemini"

            }

        )


collaborative_engine = CollaborativeEngine()