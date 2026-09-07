"""
==========================================================================
AgriMind

TRUSTAI Decision Engine

Chooses between auto-execution, human review, and rejection by
expected utility instead of a fixed trust threshold (bayesian.txt,
section 13: "Do NOT use if trust > 0.8: execute"), so the same
posterior trust can lead to a different decision depending on what
is actually at stake for that action.

    P(fail)   = 1 - trust_mean + uncertainty_margin * trust_std
    EU(auto)  = (1 - P(fail)) * benefit  -  P(fail) * failure_cost
    EU(review)=      review_catch_rate * benefit  -  review_cost
    EU(reject)=    - reject_cost

The uncertainty margin means a brand-new agent (wide posterior) is
treated more cautiously than a long-proven one at the same mean
trust -- two agents can share a trust_mean of 0.7 and still receive
different decisions if one of them has far less history behind it.

Author : AgriMind Team
==========================================================================
"""

from app.config import ai_settings
from app.governance.models import GovernanceDecision


class DecisionEngine:

    ####################################################################
    # Decide
    ####################################################################

    def decide(self, posterior, risk):

        p_fail = (
            1
            - posterior.mean
            + ai_settings.GOVERNANCE_UNCERTAINTY_MARGIN * posterior.std
        )

        p_fail = max(0.0, min(1.0, p_fail))

        eu_auto = (
            (1 - p_fail) * risk.benefit
            - p_fail * risk.failure_cost
        )

        eu_review = (
            risk.benefit * ai_settings.GOVERNANCE_REVIEW_CATCH_RATE
            - risk.review_cost
        )

        eu_reject = -risk.reject_cost

        utilities = {
            "auto_execute": round(eu_auto, 3),
            "human_review": round(eu_review, 3),
            "reject": round(eu_reject, 3)
        }

        action = max(utilities, key=utilities.get)

        rationale = (
            f"P(fail)={p_fail:.2f} from trust={posterior.mean:.2f} "
            f"(+/-{posterior.std:.2f}) on a "
            f"{risk.risk_level.lower()}-risk {risk.category} action "
            f"=> {action} "
            f"(EU auto={utilities['auto_execute']}, "
            f"review={utilities['human_review']}, "
            f"reject={utilities['reject']})."
        )

        return GovernanceDecision(
            action=action,
            p_fail=round(p_fail, 4),
            utilities=utilities,
            rationale=rationale
        )


##########################################################################
# Singleton
##########################################################################

decision_engine = DecisionEngine()
