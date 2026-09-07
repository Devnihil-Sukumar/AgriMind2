"""
==========================================================================
AgriMind

Explainable Recommendation Model

Module 5G

Stores the final explainability report.

Author : AgriMind Team
==========================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class Explanation:

    """
    Final Explainability Report
    """

    ####################################################################
    # Executive Decision
    ####################################################################

    executive_decision: str

    executive_summary: str

    recommendation: str

    ####################################################################
    # Explainability
    ####################################################################

    explanation: str

    reasoning_summary: str

    ####################################################################
    # Decision Trace
    ####################################################################

    decision_trace: List[Dict] = field(

        default_factory=list

    )

    ####################################################################
    # Evidence
    ####################################################################

    evidence: Dict[str, Any] = field(

        default_factory=dict

    )

    ####################################################################
    # Risks & Opportunities
    ####################################################################

    risks: List[str] = field(

        default_factory=list

    )

    opportunities: List[str] = field(

        default_factory=list

    )

    ####################################################################
    # Alternatives
    ####################################################################

    rejected_alternatives: List[Dict] = field(

        default_factory=list

    )

    ####################################################################
    # Limitations
    ####################################################################

    limitations: List[Dict] = field(

        default_factory=list

    )

    ####################################################################
    # Monitoring Plan
    ####################################################################

    monitoring_plan: List[Dict] = field(

        default_factory=list

    )

    ####################################################################
    # Confidence
    ####################################################################

    confidence_breakdown: Dict[str, Any] = field(

        default_factory=dict

    )

    overall_confidence: float = 0.0

    ####################################################################
    # Metadata
    ####################################################################

    model: str = "Qwen"

    module: str = "Explainable Recommendation"

    version: str = "2.0"

    status: str = "completed"

    ####################################################################
    # Serialize
    ####################################################################

    def to_dict(self):

        return {

            ########################################################
            # Executive
            ########################################################

            "executive_decision":

                self.executive_decision,

            "executive_summary":

                self.executive_summary,

            "recommendation":

                self.recommendation,

            ########################################################
            # Explanation
            ########################################################

            "explanation":

                self.explanation,

            "reasoning_summary":

                self.reasoning_summary,

            ########################################################
            # Decision Trace
            ########################################################

            "decision_trace":

                self.decision_trace,

            ########################################################
            # Evidence
            ########################################################

            "evidence":

                self.evidence,

            ########################################################
            # Risks
            ########################################################

            "risks":

                self.risks,

            ########################################################
            # Opportunities
            ########################################################

            "opportunities":

                self.opportunities,

            ########################################################
            # Alternatives
            ########################################################

            "rejected_alternatives":

                self.rejected_alternatives,

            ########################################################
            # Limitations
            ########################################################

            "limitations":

                self.limitations,

            ########################################################
            # Monitoring
            ########################################################

            "monitoring_plan":

                self.monitoring_plan,

            ########################################################
            # Confidence
            ########################################################

            "confidence_breakdown":

                self.confidence_breakdown,

            "overall_confidence":

                self.overall_confidence,

            ########################################################
            # Metadata
            ########################################################

            "model":

                self.model,

            "module":

                self.module,

            "version":

                self.version,

            "status":

                self.status

        }