"""
==========================================================================
AgriMind

TRUSTAI Runtime Governance Layer

Sits between the executor and every agent it calls (bayesian.txt:
"TRUSTAI: A Runtime Bayesian Governance Layer for Autonomous AI
Agents"):

    Executor -> TRUSTAI.review()   -> auto_execute / reject
                     |
                Tool Execution
                     |
    Executor -> TRUSTAI.record_outcome() -> evidence -> posterior
                                             update -> audit log

review() is the pre-execution interception point: it can veto a
call outright (a "reject" decision) before the agent ever runs.
record_outcome() is the post-execution learning point: it turns the
result into evidence, updates that agent's Bayesian trust posterior,
and appends the full decision trace to the audit log.

Author : AgriMind Team
==========================================================================
"""

from app.governance.models import GovernanceRecord
from app.governance.trust_engine import trust_engine
from app.governance.risk_engine import risk_engine
from app.governance.evidence import evidence_engine
from app.governance.decision_engine import decision_engine
from app.governance.audit_logger import audit_logger


##########################################################################
# Agent -> Category
##########################################################################

AGENT_CATEGORY = {

    "WeatherAgent": "data_collector",
    "SoilAgent": "data_collector",
    "SatelliteAgent": "data_collector",
    "MarketAgent": "data_collector",
    "HistoricalAgent": "data_collector",

    "ExecutiveAgent": "executive",

    "RecommendationAgent": "recommendation"

}


class TrustAI:

    def category_of(self, agent_name):
        return AGENT_CATEGORY.get(agent_name, "data_collector")

    ####################################################################
    # Pre-Execution Review
    ####################################################################

    def review(self, agent_name):

        category = self.category_of(agent_name)

        posterior = trust_engine.posterior(agent_name, category)
        risk = risk_engine.assess(category)
        decision = decision_engine.decide(posterior, risk)

        record = GovernanceRecord(

            agent=agent_name,

            category=category,

            stage="pre",

            prior_mean=posterior.mean,

            posterior_mean=posterior.mean,

            evidence=None,

            risk=risk,

            decision=decision

        )

        audit_logger.log(record)

        return record

    ####################################################################
    # Post-Execution Evidence + Posterior Update
    ####################################################################

    def record_outcome(self, agent_name, result):

        category = self.category_of(agent_name)

        prior = trust_engine.posterior(agent_name, category)

        evidence = evidence_engine.from_result(category, result)

        posterior = trust_engine.update(agent_name, category, evidence)

        risk = risk_engine.assess(category)

        decision = decision_engine.decide(posterior, risk)

        record = GovernanceRecord(

            agent=agent_name,

            category=category,

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
    # Trust Snapshot (pipeline-level governance summary)
    ####################################################################

    def snapshot(self):

        agents = {}

        for agent_name, category in AGENT_CATEGORY.items():

            posterior = trust_engine.posterior(agent_name, category)

            agents[agent_name] = {

                "category": category,

                "trust_mean": round(posterior.mean, 4),

                "trust_std": round(posterior.std, 4)

            }

        return agents


##########################################################################
# Singleton
##########################################################################

trustai = TrustAI()
