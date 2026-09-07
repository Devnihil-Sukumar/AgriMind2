"""
==========================================================================
AgriMind

TRUSTAI Bayesian Belief Engine

Maintains a Beta-Binomial posterior over each agent's trustworthiness.

Posterior ~ Beta(alpha, beta), mean = alpha / (alpha + beta).

Two ideas from bayesian.txt are implemented here in closed form,
deliberately without a full hierarchical MCMC fit (sections 8 and
11 both call for a lightweight runtime approximation instead):

1. Hierarchical cold-start prior -- a new agent does not start
   blind at a flat population prior. It inherits the *current*
   posterior of its category (data_collector / executive /
   recommendation) as its own starting prior. Since the category
   posterior itself is a running pool of every agent in that
   category's evidence, this is empirical-Bayes partial pooling:
   new agents borrow strength from similar ones.

2. Sequential trust decay -- every update first shrinks the
   existing posterior back toward the category prior before folding
   in new evidence, so a long run of old evidence gradually loses
   influence instead of permanently anchoring trust.

Author : AgriMind Team
==========================================================================
"""

from app.config import ai_settings
from app.governance.models import TrustPosterior
from app.governance.trust_state import trust_state_store


class TrustEngine:

    ####################################################################
    # Constructor
    #
    # Defaults to the shared agent-trust store so existing callers are
    # unaffected. app/learning/continuous_learning_engine.py injects a
    # separate store to run the exact same Beta-Binomial machinery
    # over a different key space (crops instead of agents) without
    # mixing the two in one state file.
    ####################################################################

    def __init__(self, store=None):

        self.store = store or trust_state_store

    ####################################################################
    # Priors
    ####################################################################

    def _population_prior(self):

        return (
            ai_settings.GOVERNANCE_PRIOR_ALPHA,
            ai_settings.GOVERNANCE_PRIOR_BETA
        )

    def _category_prior(self, category):

        stored = self.store.get_category(category)

        if stored:
            return stored["alpha"], stored["beta"]

        return self._population_prior()

    ####################################################################
    # Read-Only Posterior
    ####################################################################

    def posterior(self, agent_name, category):

        stored = self.store.get_agent(agent_name)

        if stored:
            alpha, beta = stored["alpha"], stored["beta"]
        else:
            alpha, beta = self._category_prior(category)

        return TrustPosterior(
            agent=agent_name,
            category=category,
            alpha=alpha,
            beta=beta
        )

    ####################################################################
    # Update With Evidence
    ####################################################################

    def update(self, agent_name, category, evidence):

        prior_alpha, prior_beta = self._category_prior(category)

        stored = self.store.get_agent(agent_name)

        if stored:

            alpha, beta = stored["alpha"], stored["beta"]

            decay = ai_settings.GOVERNANCE_TRUST_DECAY

            alpha = prior_alpha + decay * (alpha - prior_alpha)
            beta = prior_beta + decay * (beta - prior_beta)

            updates = stored.get("updates", 0)

        else:

            alpha, beta = prior_alpha, prior_beta
            updates = 0

        if evidence.positive:
            alpha += evidence.weight
        else:
            beta += evidence.weight

        updates += 1

        self.store.set_agent(
            agent_name,
            alpha,
            beta,
            updates
        )

        ############################################################
        # The category posterior absorbs a (small) fraction of the
        # same evidence so it keeps pooling statistical strength
        # across every agent that shares it, without letting any one
        # agent's run dominate the group estimate.
        ############################################################

        cat_alpha, cat_beta = self._category_prior(category)

        pooling = ai_settings.GOVERNANCE_POOLING_STRENGTH

        if evidence.positive:
            cat_alpha += evidence.weight * pooling
        else:
            cat_beta += evidence.weight * pooling

        self.store.set_category(
            category,
            cat_alpha,
            cat_beta
        )

        return TrustPosterior(
            agent=agent_name,
            category=category,
            alpha=alpha,
            beta=beta
        )


##########################################################################
# Singleton
##########################################################################

trust_engine = TrustEngine()
