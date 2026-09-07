"""
==========================================================================
AgriMind

TRUSTAI Audit Logger

Appends one JSON record per governance decision so the full
prior -> evidence -> posterior -> risk -> utility -> decision chain
(bayesian.txt, section 15) stays inspectable after the run ends,
without requiring a live dashboard to view it.

Author : AgriMind Team
==========================================================================
"""

import json
import os
import time
from dataclasses import asdict

LOG_PATH = os.path.join("logs", "trustai_audit.jsonl")


class GovernanceAuditLogger:

    def __init__(self, path=LOG_PATH):
        self.path = path

    ####################################################################
    # Log
    ####################################################################

    def log(self, record):

        os.makedirs(
            os.path.dirname(self.path) or ".",
            exist_ok=True
        )

        entry = {

            "timestamp": time.time(),

            "agent": record.agent,

            "category": record.category,

            "stage": record.stage,

            "prior_mean": round(record.prior_mean, 4),

            "posterior_mean": round(record.posterior_mean, 4),

            "evidence": (
                asdict(record.evidence)
                if record.evidence else None
            ),

            "risk": asdict(record.risk),

            "decision": asdict(record.decision)

        }

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


##########################################################################
# Singleton
##########################################################################

audit_logger = GovernanceAuditLogger()
