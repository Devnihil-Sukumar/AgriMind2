"""
==========================================================================
AgriMind

TRUSTAI Evidence Engine

Converts a specialist / executive / recommendation result into
evidence for the Bayesian trust update.

Not every outcome is equally informative (bayesian.txt, section 8):
a confident completion from the higher-stakes recommendation stage
should move trust more than the same confidence from a routine data
fetch, a deterministic fallback is weaker support than a real model
run, and an "unavailable" upstream source is a much milder signal
than the agent itself failing.

Author : AgriMind Team
==========================================================================
"""

from app.config import ai_settings
from app.governance.models import Evidence
from app.governance.risk_engine import CATEGORY_RISK


class EvidenceEngine:

    ####################################################################
    # From Result
    ####################################################################

    def from_result(self, category, result):

        profile = CATEGORY_RISK.get(
            category,
            CATEGORY_RISK["data_collector"]
        )

        role_weight = profile["benefit_multiplier"]

        base = ai_settings.GOVERNANCE_BASE_EVIDENCE_WEIGHT

        status = str(
            result.get("status", "")
        ).strip().lower()

        ############################################################
        # Completed
        ############################################################

        if status == "completed":

            confidence = float(
                result.get("confidence", 0.0) or 0.0
            )

            weight = base * max(confidence, 0.1) * role_weight

            if result.get("generation_mode") == "deterministic_fallback":

                weight *= ai_settings.GOVERNANCE_FALLBACK_DISCOUNT

                reason = (
                    "Completed via deterministic fallback "
                    "(weaker evidence, no live model reasoning)."
                )

            else:

                reason = (
                    f"Completed with confidence {confidence:.2f}."
                )

            return Evidence(
                positive=True,
                weight=weight,
                reason=reason
            )

        ############################################################
        # Unavailable
        #
        # The upstream data source produced nothing usable -- this is
        # not the agent's fault, so it is a mild reliability discount
        # rather than a failure-grade penalty.
        ############################################################

        if status == "unavailable":

            weight = (
                base
                * ai_settings.GOVERNANCE_UNAVAILABLE_PENALTY
                * role_weight
            )

            return Evidence(
                positive=False,
                weight=weight,
                reason=(
                    "Upstream data source unavailable "
                    "(mild reliability discount)."
                )
            )

        ############################################################
        # Failed / Rejected / Anything Else
        ############################################################

        weight = (
            base
            * role_weight
            * ai_settings.GOVERNANCE_FAILURE_PENALTY
        )

        return Evidence(
            positive=False,
            weight=weight,
            reason=(
                f"Execution outcome '{status or 'unknown'}' "
                "treated as a failure."
            )
        )


##########################################################################
# Singleton
##########################################################################

evidence_engine = EvidenceEngine()
