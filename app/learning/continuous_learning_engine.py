"""
==========================================================================
AgriMind

Continuous Learning Engine

Module 5H.

AgriMind has no real farmer-feedback channel yet -- no UI, no "did
you follow this advice, did it work" signal ever reaches the
pipeline. So this cannot claim to learn actual agronomic outcomes;
that would require ground truth this system does not have.

What it CAN legitimately learn from signals the pipeline already
produces is how consistently good the final recommendation itself
has been for a given crop over time: a real LLM-reasoned answer vs.
a deterministic fallback, high confidence vs. low, completed vs.
failed. That is a proxy for pipeline maturity per crop, not a proxy
for real-world yield -- crops with sparse crop-profile data or ones
the model struggles with should visibly earn less trust here than
well-covered ones.

Per your own scoping choice, this extends TRUSTAI rather than
building a parallel system: it reuses the exact same Beta-Binomial
trust engine, evidence weighting, risk profile and expected-utility
decision engine as app/governance/, just keyed by crop instead of by
agent, in its own isolated state file so the two dimensions (agent
reliability vs. crop-level recommendation quality) don't mix.

Author : AgriMind Team
==========================================================================
"""

import os

from app.governance.trust_state import TrustStateStore
from app.governance.trust_engine import TrustEngine
from app.governance.risk_engine import risk_engine
from app.governance.evidence import evidence_engine
from app.governance.decision_engine import decision_engine
from app.governance.audit_logger import audit_logger
from app.governance.models import GovernanceRecord

LEARNING_STATE_PATH = os.path.join(
    "app", "governance", "state", "crop_learning_state.json"
)

##########################################################################
# Reuse the "recommendation" risk profile verbatim -- the cost of a
# bad recommendation doesn't change depending on whether the question
# is "should we trust RecommendationAgent" or "should we trust what
# we know about this crop"; it's the same downstream action either
# way (a farmer acting on it).
##########################################################################

RISK_CATEGORY = "recommendation"


class ContinuousLearningEngine:

    def __init__(self):

        self.store = TrustStateStore(path=LEARNING_STATE_PATH)

        self.trust_engine = TrustEngine(store=self.store)

    ####################################################################
    # Record One Recommendation Outcome
    ####################################################################

    def record_recommendation_outcome(self, crop, recommendation_result):

        crop_key = str(crop or "unknown").strip().lower()

        prior = self.trust_engine.posterior(crop_key, RISK_CATEGORY)

        evidence = evidence_engine.from_result(
            RISK_CATEGORY,
            recommendation_result
        )

        posterior = self.trust_engine.update(
            crop_key,
            RISK_CATEGORY,
            evidence
        )

        risk = risk_engine.assess(RISK_CATEGORY)

        decision = decision_engine.decide(posterior, risk)

        record = GovernanceRecord(

            agent=f"crop:{crop_key}",

            category="crop_recommendation_quality",

            stage="post",

            prior_mean=prior.mean,

            posterior_mean=posterior.mean,

            evidence=evidence,

            risk=risk,

            decision=decision

        )

        audit_logger.log(record)

        return record

    ####################################################################
    # Snapshot
    ####################################################################

    def snapshot(self):

        result = {}

        for crop_key in self.store.get_all_agents():

            posterior = self.trust_engine.posterior(
                crop_key,
                RISK_CATEGORY
            )

            result[crop_key] = {

                "trust_mean": round(posterior.mean, 4),

                "trust_std": round(posterior.std, 4)

            }

        return result


##########################################################################
# Singleton
##########################################################################

continuous_learning_engine = ContinuousLearningEngine()
