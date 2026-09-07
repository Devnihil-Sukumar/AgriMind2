"""
==========================================================================
AgriMind

TRUSTAI Governance Models

Shared data structures for the runtime Bayesian governance layer.

Author : AgriMind Team
==========================================================================
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Evidence:

    positive: bool

    weight: float

    reason: str


@dataclass
class TrustPosterior:

    agent: str

    category: str

    alpha: float

    beta: float

    @property
    def mean(self):
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self):

        total = self.alpha + self.beta

        return (self.alpha * self.beta) / (
            total * total * (total + 1)
        )

    @property
    def std(self):
        return self.variance ** 0.5


@dataclass
class RiskAssessment:

    category: str

    risk_level: str

    benefit: float

    failure_cost: float

    review_cost: float

    reject_cost: float


@dataclass
class GovernanceDecision:

    # "auto_execute" | "human_review" | "reject"
    action: str

    p_fail: float

    utilities: dict

    rationale: str


@dataclass
class GovernanceRecord:

    agent: str

    category: str

    # "pre" (before execution) | "post" (after outcome is known)
    stage: str

    prior_mean: float

    posterior_mean: float

    evidence: Optional[Evidence]

    risk: RiskAssessment

    decision: GovernanceDecision
