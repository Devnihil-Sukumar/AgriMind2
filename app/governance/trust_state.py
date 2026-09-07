"""
==========================================================================
AgriMind

TRUSTAI Trust State Store

Persists per-agent and per-category Beta-Binomial trust parameters
to a JSON file so posteriors survive across runs instead of
resetting every time the process starts.

Author : AgriMind Team
==========================================================================
"""

import json
import os
import threading

STATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "state",
    "trust_state.json"
)


class TrustStateStore:

    def __init__(self, path=STATE_PATH):

        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    ####################################################################
    # Load / Save
    ####################################################################

    def _load(self):

        if not os.path.exists(self.path):
            return {"agents": {}, "categories": {}}

        try:

            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)

        except (json.JSONDecodeError, OSError):

            return {"agents": {}, "categories": {}}

    def _save(self):

        os.makedirs(
            os.path.dirname(self.path),
            exist_ok=True
        )

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    ####################################################################
    # Agent-Level State
    ####################################################################

    def get_agent(self, agent_name):
        return self._data["agents"].get(agent_name)

    def get_all_agents(self):
        return list(self._data["agents"].keys())

    def set_agent(self, agent_name, alpha, beta, updates):

        with self._lock:

            self._data["agents"][agent_name] = {
                "alpha": alpha,
                "beta": beta,
                "updates": updates
            }

            self._save()

    ####################################################################
    # Category-Level State (pooled prior)
    ####################################################################

    def get_category(self, category):
        return self._data["categories"].get(category)

    def set_category(self, category, alpha, beta):

        with self._lock:

            self._data["categories"][category] = {
                "alpha": alpha,
                "beta": beta
            }

            self._save()


##########################################################################
# Singleton
##########################################################################

trust_state_store = TrustStateStore()
