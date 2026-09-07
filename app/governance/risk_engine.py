"""
==========================================================================
AgriMind

TRUSTAI Risk Engine

Maps each governed agent category to an operational risk profile:
the benefit of a correct action, and the cost of a wrong one, a
wrong one caught by review instead, and skipping the action
altogether.

Trust and risk are deliberately kept as separate variables here --
a highly trusted agent can still warrant review before a
high-stakes action (see decision_engine.py).

Author : AgriMind Team
==========================================================================
"""

from app.config import ai_settings
from app.governance.models import RiskAssessment


##########################################################################
# Category Risk Profiles
#
# benefit_multiplier / failure_multiplier scale the base benefit and
# base failure cost (app/config/ai_settings.py). Data collectors are
# read-only fetches with a low blast radius; the executive decision
# and the final recommendation carry increasingly higher stakes since
# a farmer may act on them directly.
##########################################################################

CATEGORY_RISK = {

    "data_collector": {
        "risk_level": "Low",
        "benefit_multiplier": 1.0,
        "failure_multiplier": 1.0
    },

    "executive": {
        "risk_level": "Medium",
        "benefit_multiplier": 1.5,
        "failure_multiplier": 3.0
    },

    "recommendation": {
        "risk_level": "High",
        "benefit_multiplier": 2.0,
        "failure_multiplier": 6.0
    }

}


class RiskEngine:

    ####################################################################
    # Assess
    ####################################################################

    def assess(self, category):

        profile = CATEGORY_RISK.get(
            category,
            CATEGORY_RISK["data_collector"]
        )

        benefit = (
            ai_settings.GOVERNANCE_BASE_BENEFIT
            * profile["benefit_multiplier"]
        )

        failure_cost = (
            ai_settings.GOVERNANCE_BASE_FAILURE_COST
            * profile["failure_multiplier"]
        )

        reject_cost = (
            benefit
            * ai_settings.GOVERNANCE_REJECT_COST_RATIO
        )

        return RiskAssessment(

            category=category,

            risk_level=profile["risk_level"],

            benefit=benefit,

            failure_cost=failure_cost,

            review_cost=ai_settings.GOVERNANCE_REVIEW_COST,

            reject_cost=reject_cost

        )


##########################################################################
# Singleton
##########################################################################

risk_engine = RiskEngine()
